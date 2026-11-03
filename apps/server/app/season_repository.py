"""Atomically persist schedule, event provenance and both team reports per game."""

import re

from pydantic import ValidationError

from app.date_ranges import month_date_range
from app.mental import (
    MODEL_VERSION,
    TEAMS,
    MentalReport,
    NormalizedEvent,
    SeasonCoverage,
    SeasonGame,
    SeasonResponse,
)

# A result computed from a different schedule cannot replace current reports.
SCHEDULE_FIELDS = (
    "game_id",
    "game_date",
    "season",
    "series_id",
    "away_team_id",
    "home_team_id",
    "status",
    "away_runs",
    "home_runs",
)


def _validate_schedule(game: SeasonGame) -> None:
    if game.series_id == "1":
        raise ValueError("Preseason games are excluded")
    if (
        game.game_date.year != game.season
        or game.game_id[:8] != game.game_date.strftime("%Y%m%d")
        or game.game_id[8:10] != game.away_team_id
        or game.game_id[10:12] != game.home_team_id
    ):
        raise ValueError("Game ID, date, season and team fields must agree")
    if (
        game.away_team_id not in TEAMS
        or game.home_team_id not in TEAMS
        or game.away_team_id == game.home_team_id
    ):
        raise ValueError("Schedule must have two distinct KBO teams")
    if game.status == "completed" and (game.away_runs is None or game.home_runs is None):
        raise ValueError("Completed schedule requires final scores")


def _schedule_identity(game: SeasonGame) -> dict:
    data = game.model_dump(mode="json")
    return {key: data[key] for key in SCHEDULE_FIELDS}


def _validate_reports(game: SeasonGame, reports: list[MentalReport]) -> str:
    _validate_schedule(game)
    if len(reports) != 2 or any(report.game_id != game.game_id for report in reports):
        raise ValueError("Expected two reports for the scheduled game")
    participants = {game.away_team_id, game.home_team_id}
    if len(participants) != 2 or {report.team_id for report in reports} != participants:
        raise ValueError("Reports must contain both distinct participating teams")
    first, second = reports
    if first.status != second.status or first.status not in {"ready", "incomplete"}:
        raise ValueError("Report pair must agree on ready or incomplete status")
    if any(report.model_version != MODEL_VERSION for report in reports):
        raise ValueError("Report model version is obsolete")
    if not first.source_hash or first.source_hash != second.source_hash:
        raise ValueError("Report pair must share source hash")
    if first.computed_at is None or first.computed_at != second.computed_at:
        raise ValueError("Report pair must share computation time")
    if first.status == "ready":
        if game.status != "completed" or game.away_runs is None or game.home_runs is None:
            raise ValueError("Ready reports require a completed, scored schedule")
        for report in reports:
            if (
                report.score is None
                or not 0 <= report.score <= 100
                or report.peak_score is None
                or not 0 <= report.peak_score <= 100
                or report.raw_total is None
                or not report.events
            ):
                raise ValueError("Ready report must have scores and verified events")
            raw = 0
            for event in report.events:
                raw += event.delta
                if event.score_after != max(0, min(100, 30 + raw)):
                    raise ValueError("Report timeline scores disagree with event deltas")
            if (
                report.raw_total != raw
                or report.score != report.events[-1].score_after
                or report.peak_score != max([30] + [event.score_after for event in report.events])
            ):
                raise ValueError("Report summary disagrees with event timeline")
        if [event.event_id for event in first.events] != [
            event.event_id for event in second.events
        ]:
            raise ValueError("Both reports must describe the same event stream")
    elif any(
        report.score is not None
        or report.peak_score is not None
        or report.raw_total is not None
        or report.events
        for report in reports
    ):
        raise ValueError("Incomplete reports cannot publish a score or event timeline")
    return first.status


def _current_reports(item: dict, game: SeasonGame) -> list[MentalReport]:
    if item.get("report_schedule") != _schedule_identity(game):
        return []
    try:
        reports = [MentalReport.model_validate(raw) for raw in item.get("reports", [])]
        status = _validate_reports(game, reports)
    except (ValueError, ValidationError, TypeError):
        return []
    if status != game.index_status:
        return []
    return reports


class SeasonRepository:
    def __init__(self, database):
        self.games = database["season_games"]

    async def save_schedule(self, game: SeasonGame):
        _validate_schedule(game)
        data = game.model_dump(mode="json")
        identity = _schedule_identity(game)
        unchanged = {
            "$and": [
                {"$eq": [f"$game.{key}", {"$literal": value}]} for key, value in identity.items()
            ]
        }
        # Pipeline evaluates against the current document atomically; a read/update gap
        # must not restore reports invalidated by a concurrent schedule correction.
        await self.games.update_one(
            {"_id": game.game_id},
            [
                {
                    "$set": {
                        "game": {
                            "$mergeObjects": [
                                {"$literal": data},
                                {
                                    "index_status": {
                                        "$cond": [
                                            unchanged,
                                            {"$ifNull": ["$game.index_status", "missing"]},
                                            "missing",
                                        ],
                                    }
                                },
                            ]
                        },
                        "reports": {"$cond": [unchanged, {"$ifNull": ["$reports", []]}, []]},
                        "report_schedule": {"$cond": [unchanged, "$report_schedule", "$$REMOVE"]},
                        "normalized_events": {
                            "$cond": [unchanged, "$normalized_events", "$$REMOVE"]
                        },
                        "source_counts": {"$cond": [unchanged, "$source_counts", "$$REMOVE"]},
                        "validation_reason": {
                            "$cond": [unchanged, "$validation_reason", "$$REMOVE"]
                        },
                    }
                }
            ],
            upsert=True,
        )

    async def save_reports(
        self,
        game_id: str,
        reports: list[MentalReport],
        *,
        expected_game: SeasonGame,
        normalized_events: list[dict] | None = None,
        source_counts: dict | None = None,
        validation_reason: str | None = None,
    ):
        if game_id != expected_game.game_id:
            raise ValueError("Expected schedule does not match game ID")
        status = _validate_reports(expected_game, reports)
        events = [
            NormalizedEvent.model_validate(event).model_dump(mode="json")
            for event in (normalized_events or [])
        ]
        if (
            normalized_events is not None
            and status == "ready"
            and [event["event_id"] for event in events]
            != [event.event_id for event in reports[0].events]
        ):
            raise ValueError("Persisted source events disagree with reports")
        if source_counts is not None and any(
            not isinstance(key, str) or type(value) is not int or value < 0
            for key, value in source_counts.items()
        ):
            raise ValueError("Source counts must be nonnegative integer counters")
        if validation_reason is not None and (
            not isinstance(validation_reason, str)
            or len(validation_reason) > 200
            or not re.fullmatch(r"[a-z][a-z0-9_]*", validation_reason)
        ):
            raise ValueError("Validation reason must be an internal diagnostic code")
        identity = _schedule_identity(expected_game)
        computed_at = reports[0].computed_at
        query = {
            "_id": game_id,
            **{f"game.{key}": value for key, value in identity.items()},
            "$or": [
                {"reports_computed_at": {"$exists": False}},
                {"reports_computed_at": {"$lt": computed_at}},
                # Equal timestamps are idempotent only for the same source.
                {"reports_computed_at": computed_at, "reports_source_hash": reports[0].source_hash},
            ],
        }
        result = await self.games.update_one(
            query,
            {
                "$set": {
                    "reports": [report.model_dump(mode="json") for report in reports],
                    "game.index_status": status,
                    "report_schedule": identity,
                    "reports_computed_at": computed_at,
                    "reports_source_hash": reports[0].source_hash,
                    "normalized_events": events,
                    "source_counts": source_counts or {},
                    "validation_reason": validation_reason,
                }
            },
        )
        if not result.matched_count:
            raise ValueError("Schedule changed, is missing, or a newer report is already stored")

    async def season(
        self, season: int, team_id: str | None, game_date: str | None, month: int | None = None
    ):
        if game_date is not None and month is not None:
            raise ValueError("Use game_date or month")
        query = {"game.season": season, "game.series_id": {"$ne": "1"}}
        if team_id:
            query["$or"] = [{"game.away_team_id": team_id}, {"game.home_team_id": team_id}]
        if game_date:
            query["game.game_date"] = game_date
        elif month is not None:
            query["game.game_date"] = month_date_range(season, month)
        items = await self.games.find(query).sort("_id", 1).to_list(length=2000)
        games = []
        for item in items:
            game = SeasonGame.model_validate(item["game"])
            if not _current_reports(item, game):
                game.index_status = "missing"
            games.append(game)
        completed = [game for game in games if game.status == "completed"]
        return SeasonResponse(
            season=season,
            games=games,
            coverage=SeasonCoverage(
                completed=len(completed),
                indexed=sum(game.index_status == "ready" for game in completed),
                incomplete=sum(game.index_status == "incomplete" for game in completed),
                missing=sum(game.index_status == "missing" for game in completed),
            ),
        )

    async def report(self, game_id: str, team_id: str):
        item = await self.games.find_one({"_id": game_id, "game.series_id": {"$ne": "1"}})
        if item is None:
            return None
        game = SeasonGame.model_validate(item["game"])
        if team_id not in {game.away_team_id, game.home_team_id}:
            raise ValueError("Team did not participate in game")
        for report in _current_reports(item, game):
            if report.team_id == team_id:
                return report
        return MentalReport(
            game_id=game_id,
            team_id=team_id,
            status="missing",
            reason="아직 경기 자료를 확보·검증하지 못했어요.",
        )
