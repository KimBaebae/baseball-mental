"""Worker control-flow tests use only synthetic sources and in-memory collaborators."""

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from app.mental import NormalizedEvent, SeasonCoverage, SeasonGame, score_game
from app.season_repository import _schedule_identity
from workers import backfill

RAW_SOURCE = '<span id="test_spanLiveText">RAW_SOURCE_MUST_NOT_BE_PERSISTED</span>'


def game(suffix="0"):
    return SeasonGame(
        game_id=f"20260901LGOB{suffix}",
        game_date="2026-09-01",
        season=2026,
        series_id="0",
        away_team_id="LG",
        home_team_id="OB",
        status="completed",
        away_runs=3,
        home_runs=1,
    )


def event():
    return {
        "event_id": "1:top:pa1",
        "inning": 1,
        "half": "top",
        "outs_before": 0,
        "runners_before": 0,
        "margin_before": 0,
        "offense_team_id": "LG",
        "defense_team_id": "OB",
        "outcome": "out",
    }


def stored(current_game, indexed=False):
    document = {"game": current_game.model_dump(mode="json")}
    if indexed:
        reports = score_game(
            current_game,
            [NormalizedEvent.model_validate(event())],
            complete=True,
            reason=None,
            source_hash="a" * 64,
        )
        document.update(
            reports=[report.model_dump(mode="json") for report in reports],
            report_schedule=_schedule_identity(current_game),
        )
        document["game"]["index_status"] = "ready"
    return document


def setup_worker(monkeypatch, rows, *, normalized_event=None, error=None):
    captured = {"fetches": [], "saves": [], "queries": [], "closed": False, "delays": []}

    class Cursor:
        def sort(self, key, direction):
            assert (key, direction) == ("_id", 1)
            return self

        async def to_list(self, length):
            assert length == 2000
            return copy.deepcopy(rows)

    class Games:
        def find(self, query):
            captured["queries"].append(query)
            return Cursor()

    class Repo:
        games = Games()

        async def save_reports(self, game_id, reports, **kwargs):
            captured["saves"].append(
                {
                    "game_id": game_id,
                    "reports": [report.model_dump(mode="json") for report in reports],
                    **kwargs,
                }
            )

        async def season(self, *args):
            return SimpleNamespace(
                coverage=SeasonCoverage(completed=0, indexed=0, incomplete=0, missing=0)
            )

    class Client:
        def __getitem__(self, name):
            assert name == "test_fake"
            return object()

        async def close(self):
            captured["closed"] = True

    async def connect(settings):
        return Client()

    async def sleep(delay):
        captured["delays"].append(delay)

    def fetch(base, path, params):
        captured["fetches"].append((base, path, params))
        if error:
            raise error
        return RAW_SOURCE

    def normalize(*args):
        return SimpleNamespace(
            events=[copy.deepcopy(normalized_event or event())],
            complete=True,
            reason="verified_half_outs_runners_and_final_score",
            source_counts={"relay_lines": 1, "normalized_events": 1},
        )

    monkeypatch.setattr(
        backfill,
        "Settings",
        lambda: SimpleNamespace(enable_kbo_probe=True, mongodb_database="test_fake"),
    )
    monkeypatch.setattr(backfill, "connect", connect)
    monkeypatch.setattr(backfill, "SeasonRepository", lambda database: Repo())
    monkeypatch.setattr(backfill, "fetch", fetch)
    monkeypatch.setattr(backfill, "normalize", normalize)
    monkeypatch.setattr(backfill.asyncio, "sleep", sleep)
    return captured


def run_worker(**changes):
    args = {
        "skip_schedule": True,
        "schedule_only": False,
        "retry_incomplete": False,
        "refresh": False,
        "limit": 2,
        "delay": 0.5,
    } | changes
    asyncio.run(backfill.run(SimpleNamespace(**args)))


def test_invalid_normalized_context_is_unscored_incomplete(monkeypatch):
    captured = setup_worker(
        monkeypatch, [stored(game())], normalized_event=event() | {"outs_before": 3}
    )
    run_worker()
    assert len(captured["saves"]) == 1
    saved = captured["saves"][0]
    assert saved["validation_reason"] == "invalid_event_context"
    assert saved["normalized_events"] == []
    assert all(
        report["status"] == "incomplete"
        and report["score"] is None
        and report["peak_score"] is None
        and report["raw_total"] is None
        and report["events"] == []
        for report in saved["reports"]
    )
    assert captured["closed"]


def test_worker_is_bounded_and_persists_hash_not_raw_relay(monkeypatch):
    captured = setup_worker(monkeypatch, [stored(game("0")), stored(game("1")), stored(game("2"))])
    run_worker(limit=1)
    assert len(captured["fetches"]) == len(captured["saves"]) == 1
    assert captured["delays"] == [0.5]
    saved = captured["saves"][0]
    assert saved["reports"][0]["source_hash"] == hashlib.sha256(RAW_SOURCE.encode()).hexdigest()
    assert "RAW_SOURCE_MUST_NOT_BE_PERSISTED" not in json.dumps(saved, default=str)
    assert captured["queries"][0]["game.status"] == "completed"
    assert captured["queries"][0]["game.season"] == 2026
    assert captured["queries"][0]["game.series_id"] == {"$ne": "1"}
    assert captured["closed"]


def test_resume_skips_valid_pair_but_recomputes_stale_pair(monkeypatch):
    valid, stale = stored(game("0"), indexed=True), stored(game("1"), indexed=True)
    stale["reports"][0]["model_version"] = "obsolete"
    captured = setup_worker(monkeypatch, [valid, stale])
    run_worker()
    assert [request[2]["gameId"] for request in captured["fetches"]] == ["20260901LGOB1"]
    assert [saved["game_id"] for saved in captured["saves"]] == ["20260901LGOB1"]


def test_http_failure_surfaces_without_publishing_fake_success(monkeypatch):
    captured = setup_worker(
        monkeypatch, [stored(game())], error=URLError("synthetic network failure")
    )
    with pytest.raises(URLError, match="synthetic network failure"):
        run_worker()
    assert captured["saves"] == []
    assert len(captured["fetches"]) == 1
    assert captured["closed"]
