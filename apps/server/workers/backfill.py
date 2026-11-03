"""Resumable 2026 historical ingestion; raw relay text is never stored in the database or published."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings
from app.database import connect
from app.mental import NormalizedEvent, SeasonGame, score_game
from app.season_repository import SeasonRepository, _current_reports
from workers.normalize import normalize
from workers.probe_kbo import fetch
from workers.schedule import fetch_month

MAX_RELAY_BYTES = 2_000_000


def prepare_relay_cache(directory):
    if directory is None:
        return None
    path = Path(directory).expanduser().resolve()
    repository = Path(__file__).resolve().parents[3]
    if (
        path == repository
        or repository in path.parents
        or any((parent / ".git").exists() for parent in (path, *path.parents))
    ):
        raise ValueError("Relay cache must be outside any Git repository")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise ValueError("Existing relay cache directory must be private (0700)")
    return path


def load_relay(game, cache_dir=None, refresh=False):
    if not re.fullmatch(r"\d{8}[A-Z]{4}\d", game.game_id):
        raise ValueError("Invalid relay cache game ID")
    target = cache_dir / f"{game.game_id}.html" if cache_dir else None
    if target is not None and target.is_symlink():
        raise ValueError("Relay cache files must not be symlinks")
    if target is not None and target.exists() and not refresh:
        with target.open("rb") as stream:
            raw = stream.read(MAX_RELAY_BYTES + 1)
        if len(raw) > MAX_RELAY_BYTES:
            raise ValueError("Cached relay exceeds size limit")
        target.chmod(0o600)
        return raw.decode("utf-8")
    html = fetch(
        "https://www.koreabaseball.com",
        "/Game/LiveTextView2.aspx",
        {"leagueId": "1", "seriesId": game.series_id, "gameId": game.game_id, "gyear": "2026"},
    )
    raw = html.encode("utf-8")
    if len(raw) > MAX_RELAY_BYTES:
        raise ValueError("Relay exceeds cache size limit")
    if target is not None:
        descriptor, temporary = tempfile.mkstemp(prefix=".relay-", dir=cache_dir)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(raw)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return html


async def run(args):
    settings = Settings()
    if not settings.enable_kbo_probe:
        raise ValueError("Historical source verification requires ENABLE_KBO_PROBE=true")
    cache_dir = prepare_relay_cache(getattr(args, "relay_cache_dir", None))
    client = await connect(settings)
    db = client[settings.mongodb_database]
    repo = SeasonRepository(db)
    today = (datetime.now(UTC) + timedelta(hours=9)).date()
    try:
        if not args.skip_schedule:
            for month in range(1, min(12, today.month if today.year == 2026 else 12) + 1):
                for group in ("regular", "postseason"):
                    result = await asyncio.to_thread(fetch_month, 2026, month, group)
                    for row in result.games:
                        await repo.save_schedule(SeasonGame.model_validate(row))
                    await db.season_imports.update_one(
                        {"_id": f"2026-{month:02}-{group}"},
                        {
                            "$set": {
                                "collected_at": datetime.now(UTC),
                                "games": len(result.games),
                                "cancelled_without_id": result.cancelled_without_id,
                                "unresolved_without_id": result.unresolved_without_id,
                                "non_game_rows": result.non_game_rows,
                            }
                        },
                        upsert=True,
                    )
                    print(
                        json.dumps(
                            {
                                "stage": "schedule",
                                "month": month,
                                "group": group,
                                "games": len(result.games),
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    await asyncio.sleep(args.delay)
        if args.schedule_only:
            return
        rows = (
            await repo.games.find(
                {
                    "game.season": 2026,
                    "game.status": "completed",
                    "game.series_id": {"$ne": "1"},
                    "game.game_date": {"$lte": today.isoformat()},
                }
            )
            .sort("_id", 1)
            .to_list(length=2000)
        )
        attempted = 0
        for row in rows:
            game = SeasonGame.model_validate(row["game"])
            reports = _current_reports(row, game)
            if (
                reports
                and not args.refresh
                and (not args.retry_incomplete or row["game"]["index_status"] == "ready")
            ):
                continue
            if attempted >= args.limit:
                break
            if game.away_runs is None or game.home_runs is None:
                continue
            # Only one relay request per known completed game; schedule already supplies final score.
            html = await asyncio.to_thread(load_relay, game, cache_dir, args.refresh)
            result = normalize(
                html, game.away_team_id, game.home_team_id, game.away_runs, game.home_runs
            )
            try:
                events = [NormalizedEvent.model_validate(event) for event in result.events]
            except ValidationError:
                # A parser inconsistency must never publish a score or block other games.
                events = []
                result.complete = False
                result.reason = "invalid_event_context"
            digest = hashlib.sha256(html.encode()).hexdigest()
            reports = score_game(
                game,
                events,
                complete=result.complete,
                reason=(
                    None
                    if result.complete
                    else {
                        "missing_relay": "중계 자료를 확보하지 못했어요.",
                        "review_changed_or_unknown": "비디오 판독 정정 내용을 검증하고 있어요.",
                    }.get(
                        result.reason, "경기의 주자·아웃·득점 기록을 아직 완전히 검증하지 못했어요."
                    )
                ),
                source_hash=digest,
            )
            await repo.save_reports(
                game.game_id,
                reports,
                expected_game=game,
                normalized_events=[event.model_dump(mode="json") for event in events],
                source_counts=result.source_counts,
                validation_reason=result.reason,
            )
            attempted += 1
            print(
                json.dumps(
                    {
                        "stage": "index",
                        "game_id": game.game_id,
                        "status": reports[0].status,
                        "events": len(events),
                        "attempted": attempted,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            await asyncio.sleep(args.delay)
        response = await repo.season(2026, None, None)
        print(response.coverage.model_dump_json(), flush=True)
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule-only", action="store_true")
    parser.add_argument("--skip-schedule", action="store_true")
    parser.add_argument("--retry-incomplete", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--relay-cache-dir",
        help="Opt-in private local source cache outside Git; --refresh replaces cached source",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    if not 1 <= args.limit <= 2000 or args.delay < 0.5:
        parser.error("limit must be 1..2000; delay must be at least 0.5 seconds")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
