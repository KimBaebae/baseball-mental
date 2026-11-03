from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pymongo.errors import PyMongoError

from app.config import Settings
from app.database import connect
from app.mental import TEAMS, MentalReport, SeasonResponse
from app.models import GameSnapshot
from app.repository import GameRepository
from app.season_repository import SeasonRepository


def repository(request: Request) -> GameRepository:
    if request.app.state.client is None:
        raise HTTPException(503, "Game storage is not configured")
    return GameRepository()


def season_repository(request: Request) -> SeasonRepository:
    if request.app.state.client is None:
        raise HTTPException(503, "Game storage is not configured")
    return SeasonRepository(request.app.state.client[request.app.state.database_name])


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = await connect(settings) if settings.mongodb_uri else None
        app.state.database_name = settings.mongodb_database
        try:
            yield
        finally:
            if app.state.client is not None:
                await app.state.client.close()

    app = FastAPI(title="왜저럴까 API", version="0.1.0", lifespan=lifespan)

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request) -> dict[str, str]:
        client = request.app.state.client
        if client is None:
            raise HTTPException(503, "Game storage is not configured")
        try:
            await client.admin.command("ping")
        except PyMongoError:
            raise HTTPException(503, "Game storage is unavailable") from None
        return {"status": "ok"}

    @app.get("/v1/games", response_model=list[GameSnapshot], tags=["games"])
    async def list_games(
        game_date: Annotated[date, Query()],
        repo: Annotated[GameRepository, Depends(repository)],
    ):
        try:
            return await repo.list_games(game_date)
        except PyMongoError:
            raise HTTPException(503, "Game storage is unavailable") from None

    @app.get("/v1/games/{game_id}", response_model=GameSnapshot, tags=["games"])
    async def get_game(game_id: str, repo: Annotated[GameRepository, Depends(repository)]):
        try:
            game = await repo.get_game(game_id)
        except PyMongoError:
            raise HTTPException(503, "Game storage is unavailable") from None
        if game is None:
            raise HTTPException(404, "Game not found")
        return game

    @app.get("/v1/seasons/{season}/games", response_model=SeasonResponse, tags=["mental"])
    async def season_games(
        season: int,
        repo: Annotated[SeasonRepository, Depends(season_repository)],
        team_id: str | None = None,
        game_date: date | None = None,
    ):
        if season != 2026:
            raise HTTPException(422, "Only the 2026 season is supported")
        if team_id is not None and team_id not in TEAMS:
            raise HTTPException(422, "Unknown KBO team")
        if game_date and game_date.year != season:
            raise HTTPException(422, "Date must belong to requested season")
        try:
            return await repo.season(season, team_id, game_date.isoformat() if game_date else None)
        except PyMongoError:
            raise HTTPException(503, "Game storage is unavailable") from None

    @app.get("/v1/games/{game_id}/mental", response_model=MentalReport, tags=["mental"])
    async def mental_report(
        game_id: str,
        team_id: str,
        repo: Annotated[SeasonRepository, Depends(season_repository)],
    ):
        if team_id not in TEAMS:
            raise HTTPException(422, "Unknown KBO team")
        try:
            report = await repo.report(game_id, team_id)
        except ValueError:
            raise HTTPException(422, "Team did not participate in game") from None
        except PyMongoError:
            raise HTTPException(503, "Game storage is unavailable") from None
        if report is None:
            raise HTTPException(404, "Game not found")
        return report

    return app


app = create_app()
