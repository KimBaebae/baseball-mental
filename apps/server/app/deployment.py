"""Read-only configuration and HTTP deployment checks. Never print credentials or response bodies."""

import argparse
import asyncio
import os
from datetime import date
from urllib.parse import urlsplit

import httpx
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.config import Settings
from app.models import GameSnapshot


async def preflight(check_db: bool = False) -> None:
    settings = Settings()
    if settings.app_env == "local":
        raise ValueError("Set APP_ENV=staging or production for deployment preflight")
    if check_db:
        client = AsyncMongoClient(
            settings.mongodb_uri.get_secret_value(), serverSelectionTimeoutMS=5000
        )
        try:
            # No Beanie initialization: deployment preflight does not create indexes or write data.
            await client.admin.command("ping")
        finally:
            await client.close()


def smoke(base_url: str, game_date: date, token: str | None = None) -> None:
    url = urlsplit(base_url)
    if url.scheme not in {"http", "https"} or not url.hostname:
        raise ValueError("Expected an HTTP(S) service URL")
    if url.scheme != "https" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Remote services require HTTPS")
    if url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        raise ValueError("Use the service origin without credentials, query, fragment or path")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=10) as client:
        for endpoint in ("/health/live", "/health/ready"):
            response = client.get(endpoint)
            response.raise_for_status()
            if response.json() != {"status": "ok"}:
                raise ValueError("Unexpected health response")
        response = client.get("/v1/games", params={"game_date": game_date.isoformat()})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise TypeError("Unexpected games response")
        for snapshot in payload:
            GameSnapshot.model_validate(snapshot)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    pre = subcommands.add_parser("preflight")
    pre.add_argument("--check-db", action="store_true")
    smoke_parser = subcommands.add_parser("smoke")
    smoke_parser.add_argument("base_url")
    smoke_parser.add_argument("--game-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            asyncio.run(preflight(args.check_db))
        else:
            smoke(args.base_url, args.game_date, os.environ.get("SMOKE_ID_TOKEN"))
    except (ValueError, TypeError, PyMongoError, httpx.HTTPError, OSError) as error:
        # Driver/HTTP exception messages can contain URI credentials or auth headers.
        print(f"{args.command}: FAILED ({type(error).__name__}); inspect configuration and service health")
        return 1
    print(f"{args.command}: PASS (infrastructure check only, not live-data or product readiness)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
