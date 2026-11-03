import asyncio
import os
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import connect
from app.date_ranges import month_date_range
from app.main import create_app, repository, season_repository
from app.mental import SeasonCoverage, SeasonResponse
from app.repository import GameRepository
from tests.test_api import sample_snapshot
from tests.test_season_repository import reports_for, sample_game, with_database


@pytest.mark.parametrize(
    ("year", "month", "start", "end"),
    [
        (2026, 1, "2026-01-01", "2026-02-01"),
        (2024, 2, "2024-02-01", "2024-03-01"),
        (2026, 12, "2026-12-01", "2027-01-01"),
    ],
)
def test_month_bounds(year, month, start, end):
    assert month_date_range(year, month) == {"$gte": start, "$lt": end}


def test_month_api_validation_and_repository_arguments():
    calls = []

    class Repo:
        async def list_games(self, game_date=None, *, year=None, month=None):
            calls.append((game_date, year, month))
            return []

        async def season(self, season, team_id, game_date, month=None):
            calls.append((season, team_id, game_date, month))
            return SeasonResponse(
                season=season,
                games=[],
                coverage=SeasonCoverage(completed=0, indexed=0, incomplete=0, missing=0),
            )

    app = create_app(Settings(_env_file=None, mongodb_uri=None))
    app.dependency_overrides[repository] = Repo
    app.dependency_overrides[season_repository] = Repo
    with TestClient(app) as client:
        for query in [
            "",
            "?year=2026",
            "?month=1",
            "?year=2026&month=0",
            "?year=2026&month=13",
            "?year=2026&month=1.5",
            "?year=0&month=1",
            "?year=10000&month=1",
            "?game_date=2026-01-01&month=1",
            "?game_date=2026-01-01&year=2026",
            "?game_date=2026-01-01&year=2026&month=1",
        ]:
            assert client.get("/v1/games" + query).status_code == 422, query
        assert calls == []
        for month in [1, 2, 12]:
            assert client.get(f"/v1/games?year=2026&month={month}").status_code == 200
            assert calls[-1] == (None, 2026, month)
        assert client.get("/v1/games?game_date=2026-01-01").status_code == 200
        assert calls[-1] == (date(2026, 1, 1), None, None)
        for query in [
            "?month=0",
            "?month=13",
            "?month=x",
            "?month=1.5",
            "?month=1&game_date=2026-01-01",
            "?month=1&team_id=ZZ",
        ]:
            assert client.get("/v1/seasons/2026/games" + query).status_code == 422
        assert client.get("/v1/seasons/2025/games?month=1").status_code == 422
        assert client.get("/v1/seasons/2026/games?month=12&team_id=LG").status_code == 200
        assert calls[-1] == (2026, "LG", None, 12)
        assert client.get("/v1/seasons/2026/games").status_code == 200
        assert calls[-1] == (2026, None, None, None)
        assert client.get("/v1/seasons/2026/games?game_date=2026-01-01").status_code == 200
        assert calls[-1] == (2026, None, "2026-01-01", None)


@pytest.mark.integration
def test_mongo_season_month_boundaries_team_coverage_and_legacy_day():
    async def exercise(repo, database):
        for day in [
            "2026-01-01",
            "2026-01-31",
            "2026-02-01",
            "2026-11-30",
            "2026-12-01",
            "2026-12-31",
        ]:
            game = sample_game().model_copy(
                update={
                    "game_id": day.replace("-", "") + "LGOB0",
                    "game_date": date.fromisoformat(day),
                }
            )
            await repo.save_schedule(game)
            if day == "2026-01-01":
                await repo.save_reports(game.game_id, reports_for(game), expected_game=game)
        # Legacy preseason rows are still excluded from month and coverage.
        legacy = sample_game().model_dump(mode="json")
        legacy.update(game_date="2026-01-15", game_id="20260115LGOB0", series_id="1")
        await database.season_games.insert_one({"_id": legacy["game_id"], "game": legacy})
        january = await repo.season(2026, "LG", None, 1)
        assert [g.game_date.day for g in january.games] == [1, 31]
        assert january.coverage.completed == 2
        assert january.coverage.indexed == 1
        assert january.coverage.missing == 1
        assert (await repo.season(2026, "SS", None, 1)).games == []
        assert len((await repo.season(2026, None, None, 2)).games) == 1
        assert len((await repo.season(2026, None, None, 12)).games) == 2
        assert (await repo.season(2026, None, None, 3)).games == []
        assert len((await repo.season(2026, None, None)).games) == 6
        assert len((await repo.season(2026, None, "2026-01-31")).games) == 1
        with pytest.raises(ValueError):
            await repo.season(2026, None, "2026-01-31", 1)

    with_database(exercise)


@pytest.mark.integration
def test_mongo_snapshot_month_more_than_100_leap_day_and_year_boundary():
    uri = os.environ.get("TEST_MONGODB_URI")
    if not uri:
        pytest.skip("TEST_MONGODB_URI is required for Mongo integration")
    settings = Settings(
        _env_file=None, mongodb_uri=uri, mongodb_database="test_month_" + uuid4().hex
    )

    async def populate():
        client = await connect(settings)
        try:
            repo = GameRepository()
            for index in range(105):
                await repo.save(
                    sample_snapshot(
                        game_id=f"202612{index // 5 + 1:02}LGOB{index % 5}",
                        game_date=date(2026, 12, index // 5 + 1),
                    )
                )
            for day in [
                date(2026, 11, 30),
                date(2026, 12, 31),
                date(2027, 1, 1),
                date(2024, 2, 29),
                date(2024, 3, 1),
            ]:
                await repo.save(
                    sample_snapshot(game_id=day.strftime("%Y%m%d") + "LGOB0", game_date=day)
                )
        finally:
            await client.close()

    async def cleanup():
        client = await connect(settings)
        try:
            await client.drop_database(settings.mongodb_database)
        finally:
            await client.close()

    try:
        asyncio.run(populate())
        with TestClient(create_app(settings)) as client:
            response = client.get("/v1/games?year=2026&month=12")
            assert response.status_code == 200
            assert len(response.json()) == 106
            assert all(g["game_date"].startswith("2026-12-") for g in response.json())
            assert len(client.get("/v1/games?year=2027&month=1").json()) == 1
            assert client.get("/v1/games?year=2026&month=2").json() == []
            leap = client.get("/v1/games?year=2024&month=2").json()
            assert [g["game_date"] for g in leap] == ["2024-02-29"]
            assert len(client.get("/v1/games?game_date=2026-12-31").json()) == 1
    finally:
        asyncio.run(cleanup())
