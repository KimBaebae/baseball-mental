"""Versioned entertainment index; independent of attendance and personal records."""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

MODEL_VERSION = "kbo-mental-v1"
TEAMS = {"LG", "OB", "KT", "SS", "NC", "HH", "LT", "HT", "SK", "WO"}
IndexStatus = Literal["ready", "incomplete", "missing"]
Outcome = Literal[
    "out",
    "strikeout",
    "double_play",
    "triple_play",
    "strikeout_reached",
    "runner_advance",
    "hit",
    "walk",
    "home_run",
    "error",
    "wild_pitch",
    "passed_ball",
    "balk",
    "stolen_base",
    "caught_stealing",
    "fielders_choice",
    "hit_by_pitch",
    "sacrifice",
]


class SeasonGame(BaseModel):
    game_id: str = Field(pattern=r"^\d{8}[A-Z]{4}\d$")
    game_date: date
    season: int = 2026
    series_id: str
    away_team_id: str
    home_team_id: str
    status: Literal["completed", "scheduled", "cancelled", "unknown"]
    away_runs: int | None = Field(default=None, ge=0)
    home_runs: int | None = Field(default=None, ge=0)
    venue: str | None = None
    index_status: IndexStatus = "missing"


class NormalizedEvent(BaseModel):
    event_id: str
    inning: int = Field(ge=1, le=30)
    half: Literal["top", "bottom"]
    outs_before: int = Field(ge=0, le=2)
    runners_before: int = Field(ge=0, le=3)
    margin_before: int
    offense_team_id: str
    defense_team_id: str
    outcome: Outcome
    batter_name: str | None = None


class MentalEvent(BaseModel):
    event_id: str
    inning: int
    half: Literal["top", "bottom"]
    outcome: Outcome
    delta: int
    score_after: int
    batter_name: str | None = None


class MentalReport(BaseModel):
    game_id: str
    team_id: str
    status: IndexStatus
    reason: str | None = None
    score: int | None = None
    peak_score: int | None = None
    raw_total: int | None = None
    model_version: str = MODEL_VERSION
    events: list[MentalEvent] = Field(default_factory=list)
    computed_at: AwareDatetime | None = None
    source_hash: str | None = None


class SeasonCoverage(BaseModel):
    completed: int
    indexed: int
    incomplete: int
    missing: int


class SeasonResponse(BaseModel):
    season: int
    games: list[SeasonGame]
    coverage: SeasonCoverage


def score_game(
    game: SeasonGame,
    events: list[NormalizedEvent],
    *,
    complete: bool,
    reason: str | None,
    source_hash: str,
) -> list[MentalReport]:
    """Publish only a fully validated event stream. Each team has its own perspective."""
    now = datetime.now(UTC)
    teams = [game.away_team_id, game.home_team_id]
    if game.status != "completed" or not complete or not events:
        return [
            MentalReport(
                game_id=game.game_id,
                team_id=team,
                status="incomplete",
                reason=reason or "검증된 경기 이벤트가 부족해요.",
                computed_at=now,
                source_hash=source_hash,
            )
            for team in teams
        ]
    if len({event.event_id for event in events}) != len(events):
        raise ValueError("Duplicate normalized events")
    base = {
        "out": 6,
        "strikeout": 8,
        "double_play": 18,
        "triple_play": 26,
        "strikeout_reached": -4,
        "runner_advance": 0,
        "hit": -10,
        "walk": -4,
        "home_run": -20,
        "error": -12,
        "wild_pitch": -6,
        "passed_ball": -6,
        "balk": -4,
        "stolen_base": -4,
        "caught_stealing": 10,
        "fielders_choice": 6,
        "hit_by_pitch": -4,
        "sacrifice": 2,
    }
    reports = []
    for team in teams:
        raw = 0
        peak = 30
        timeline = []
        for event in events:
            if {event.offense_team_id, event.defense_team_id} != set(teams):
                raise ValueError("Event teams disagree with scheduled game")
            # Integer twentieths avoid platform-specific floating-point rounding.
            weight = 20 + (12 if event.inning >= 7 and abs(event.margin_before) <= 2 else 0)
            weight += 3 * event.runners_before + (4 if event.outs_before == 2 else 0)
            weighted = (abs(base[event.outcome]) * weight + 10) // 20
            sign = 1 if base[event.outcome] > 0 else -1
            delta = weighted * sign * (1 if team == event.offense_team_id else -1)
            raw += delta
            score = max(0, min(100, 30 + raw))
            peak = max(peak, score)
            timeline.append(
                MentalEvent(
                    event_id=event.event_id,
                    inning=event.inning,
                    half=event.half,
                    outcome=event.outcome,
                    delta=delta,
                    score_after=score,
                    batter_name=event.batter_name,
                )
            )
        reports.append(
            MentalReport(
                game_id=game.game_id,
                team_id=team,
                status="ready",
                score=timeline[-1].score_after,
                peak_score=peak,
                raw_total=raw,
                events=timeline,
                computed_at=now,
                source_hash=source_hash,
            )
        )
    return reports
