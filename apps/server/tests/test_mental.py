from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, season_repository
from app.mental import MentalReport, NormalizedEvent, SeasonGame, score_game


def game():
    return SeasonGame(
        game_id="20260901LGOB0",
        game_date=date(2026, 9, 1),
        series_id="0",
        away_team_id="LG",
        home_team_id="OB",
        status="completed",
    )


def event(**changes):
    return NormalizedEvent(
        **(
            {
                "event_id": "1",
                "inning": 3,
                "half": "top",
                "outs_before": 0,
                "runners_before": 0,
                "margin_before": 0,
                "offense_team_id": "LG",
                "defense_team_id": "OB",
                "outcome": "out",
            }
            | changes
        )
    )


def test_both_perspectives_and_late_pressure():
    early = score_game(game(), [event()], complete=True, reason=None, source_hash="a")
    late = score_game(
        game(),
        [event(inning=9, outs_before=2, runners_before=3)],
        complete=True,
        reason=None,
        source_hash="b",
    )
    assert [r.score for r in early] == [36, 24]
    assert late[0].raw_total > early[0].raw_total
    assert early[0].raw_total == -early[1].raw_total
    # No user, attendance, session or watch-start argument is needed.
    assert len(early) == 2


def test_incomplete_is_not_zero_and_duplicate_is_rejected():
    reports = score_game(game(), [event()], complete=False, reason="unsupported", source_hash="a")
    assert all(r.score is None and r.events == [] and r.status == "incomplete" for r in reports)
    with pytest.raises(ValueError, match="Duplicate"):
        score_game(game(), [event(), event()], complete=True, reason=None, source_hash="a")


def test_recovery_and_raw_history_not_lost_at_bounds():
    reports = score_game(
        game(),
        [event(event_id=str(n), outcome="home_run") for n in range(7)],
        complete=True,
        reason=None,
        source_hash="a",
    )
    assert reports[0].score == 0 and reports[0].raw_total == -140
    assert reports[1].score == 100 and reports[1].peak_score == 100


def test_public_mental_api_no_attendance_gate_and_missing_state():
    class Repo:
        async def report(self, game_id, team_id):
            if game_id == "missing":
                return None
            if team_id == "KT":
                raise ValueError()
            return MentalReport(game_id=game_id, team_id=team_id, status="missing")

        async def season(self, season, team_id, game_date):
            return {
                "season": season,
                "games": [game()],
                "coverage": {"completed": 1, "indexed": 0, "incomplete": 0, "missing": 1},
            }

    app = create_app(Settings(_env_file=None, mongodb_uri=None))
    app.dependency_overrides[season_repository] = Repo
    with TestClient(app) as client:
        response = client.get("/v1/games/20260901LGOB0/mental?team_id=LG")
        assert response.status_code == 200 and response.json()["score"] is None
        assert client.get("/v1/games/missing/mental?team_id=LG").status_code == 404
        assert client.get("/v1/games/20260901LGOB0/mental?team_id=KT").status_code == 422
        assert client.get("/v1/seasons/2026/games").json()["coverage"]["missing"] == 1
        assert client.get("/v1/seasons/2025/games").status_code == 422
        assert client.get("/v1/seasons/2026/games?game_date=2025-01-01").status_code == 422


def test_triple_play_and_strikeout_reached_have_distinct_effects():
    triple = score_game(
        game(), [event(outcome="triple_play")], complete=True, reason=None, source_hash="a"
    )
    reached = score_game(
        game(), [event(outcome="strikeout_reached")], complete=True, reason=None, source_hash="a"
    )
    assert triple[0].raw_total == 26
    assert reached[0].raw_total == -4
    assert reached[0].events[0].outcome == "strikeout_reached"


def test_explicit_neutral_runner_advance_does_not_invent_stress_change():
    reports = score_game(
        game(), [event(outcome="runner_advance")], complete=True, reason=None, source_hash="a"
    )
    assert all(report.score == 30 and report.raw_total == 0 for report in reports)
