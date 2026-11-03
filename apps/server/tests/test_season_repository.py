import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pymongo import AsyncMongoClient

from app.mental import NormalizedEvent, SeasonGame, score_game
from app.season_repository import SeasonRepository


def sample_game():
    return SeasonGame(
        game_id="20260901LGOB0",
        game_date="2026-09-01",
        series_id="0",
        away_team_id="LG",
        home_team_id="OB",
        status="completed",
        away_runs=3,
        home_runs=1,
        venue="잠실",
    )


def sample_events():
    return [
        NormalizedEvent(
            event_id="synthetic:1",
            inning=1,
            half="top",
            outs_before=0,
            runners_before=0,
            margin_before=0,
            offense_team_id="LG",
            defense_team_id="OB",
            outcome="out",
        )
    ]


def reports_for(game, when=None, source="a" * 64, complete=True):
    reports = score_game(
        game, sample_events(), complete=complete, reason="synthetic fixture", source_hash=source
    )
    when = when or datetime.now(UTC)
    return [report.model_copy(update={"computed_at": when}) for report in reports]


def with_database(body):
    uri = os.environ.get("TEST_MONGODB_URI")
    if not uri:
        pytest.skip("TEST_MONGODB_URI is required for Mongo integration")

    async def run():
        client = AsyncMongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True)
        name = "test_season_" + uuid4().hex
        try:
            database = client[name]
            await body(SeasonRepository(database), database)
        finally:
            await client.drop_database(name)
            await client.close()

    asyncio.run(run())


@pytest.mark.integration
def test_atomic_reports_provenance_and_schedule_correction():
    async def exercise(repo, database):
        game = sample_game()
        reports = reports_for(game)
        await repo.save_schedule(game)
        await repo.save_reports(
            game.game_id,
            reports,
            expected_game=game,
            normalized_events=[event.model_dump() for event in sample_events()],
            source_counts={"events": 1},
            validation_reason="verified_half_outs_runners_and_final_score",
        )
        item = await database.season_games.find_one({"_id": game.game_id})
        assert len(item["reports"]) == 2
        assert len(item["normalized_events"]) == 1
        assert item["source_counts"] == {"events": 1}
        assert item["validation_reason"] == "verified_half_outs_runners_and_final_score"
        assert (await repo.season(2026, None, None)).coverage.indexed == 1
        await repo.save_schedule(game)  # Refreshing unchanged source preserves index.
        assert (await repo.report(game.game_id, "LG")).status == "ready"
        corrected = game.model_copy(update={"away_runs": 4})
        await repo.save_schedule(corrected)
        assert (await repo.report(game.game_id, "LG")).status == "missing"
        assert (await repo.season(2026, None, None)).coverage.missing == 1
        with pytest.raises(ValueError, match="Schedule changed"):
            await repo.save_reports(game.game_id, reports, expected_game=game)
        item = await database.season_games.find_one({"_id": game.game_id})
        assert item["reports"] == []
        assert "normalized_events" not in item
        assert "source_counts" not in item
        assert "validation_reason" not in item

    with_database(exercise)


@pytest.mark.integration
def test_same_score_new_source_wins_and_obsolete_model_is_not_served():
    async def exercise(repo, database):
        game = sample_game()
        first_time = datetime.now(UTC)
        older = reports_for(game, first_time)
        newer = reports_for(game, first_time + timedelta(seconds=2), source="b" * 64)
        await repo.save_schedule(game)
        await repo.save_reports(game.game_id, newer, expected_game=game)
        await repo.save_reports(game.game_id, newer, expected_game=game)  # Idempotent retry.
        with pytest.raises(ValueError, match="newer report"):
            await repo.save_reports(game.game_id, older, expected_game=game)
        assert (await repo.report(game.game_id, "OB")).source_hash == "b" * 64
        await database.season_games.update_one(
            {"_id": game.game_id}, {"$set": {"reports.0.model_version": "old-model"}}
        )
        assert (await repo.report(game.game_id, "OB")).status == "missing"
        assert (await repo.season(2026, None, None)).coverage.missing == 1

    with_database(exercise)


@pytest.mark.integration
def test_rejects_incoherent_report_pair_and_keeps_incomplete_unscored():
    async def exercise(repo, database):
        game = sample_game()
        valid = reports_for(game)
        await repo.save_schedule(game)
        for invalid in [
            [valid[0], valid[0]],
            [valid[0], valid[1].model_copy(update={"status": "incomplete"})],
            [valid[0], valid[1].model_copy(update={"source_hash": "b" * 64})],
            [valid[0], valid[1].model_copy(update={"model_version": "old"})],
            [valid[0], valid[1].model_copy(update={"computed_at": None})],
        ]:
            with pytest.raises(ValueError):
                await repo.save_reports(game.game_id, invalid, expected_game=game)
        assert (await repo.report(game.game_id, "LG")).status == "missing"
        incomplete = reports_for(game, complete=False)
        await repo.save_reports(game.game_id, incomplete, expected_game=game)
        result = await repo.report(game.game_id, "LG")
        assert result.status == "incomplete" and result.score is None
        assert (await repo.season(2026, None, None)).coverage.incomplete == 1
        # Corrupt/mismatched persisted state must not leak a previously valid report.
        await database.season_games.update_one(
            {"_id": game.game_id}, {"$set": {"game.index_status": "missing"}}
        )
        assert (await repo.report(game.game_id, "LG")).status == "missing"

    with_database(exercise)


@pytest.mark.integration
def test_invalid_schedule_and_inconsistent_summary_cannot_be_persisted():
    async def exercise(repo, database):
        game = sample_game()
        for invalid in [
            game.model_copy(update={"season": 2025}),
            game.model_copy(update={"home_team_id": "LG"}),
            game.model_copy(update={"away_team_id": "ZZ"}),
            game.model_copy(update={"away_runs": None}),
        ]:
            with pytest.raises(ValueError):
                await repo.save_schedule(invalid)
        assert await database.season_games.count_documents({}) == 0
        await repo.save_schedule(game)
        reports = reports_for(game)
        reports[0] = reports[0].model_copy(update={"score": 99})
        with pytest.raises(ValueError, match="summary"):
            await repo.save_reports(game.game_id, reports, expected_game=game)
        assert (await repo.report(game.game_id, "LG")).status == "missing"

    with_database(exercise)


@pytest.mark.integration
def test_preseason_is_rejected_and_legacy_records_are_not_served():
    async def exercise(repo, database):
        regular = sample_game()
        preseason = regular.model_copy(update={"series_id": "1"})
        # Classification, not calendar date, determines exclusion.
        with pytest.raises(ValueError, match="Preseason"):
            await repo.save_schedule(preseason)
        with pytest.raises(ValueError, match="Preseason"):
            await repo.save_reports(
                preseason.game_id, reports_for(preseason), expected_game=preseason
            )
        await repo.save_schedule(regular)
        await repo.save_reports(regular.game_id, reports_for(regular), expected_game=regular)
        assert (await repo.season(2026, None, None)).coverage.indexed == 1
        # Simulate a legacy record that predates the exclusion guard.
        await database.season_games.update_one(
            {"_id": regular.game_id}, {"$set": {"game.series_id": "1"}}
        )
        for team, day in [(None, None), ("LG", "2026-09-01")]:
            response = await repo.season(2026, team, day)
            assert response.games == []
            assert response.coverage.completed == 0
            assert response.coverage.indexed == 0
        assert await repo.report(regular.game_id, "LG") is None

    with_database(exercise)
