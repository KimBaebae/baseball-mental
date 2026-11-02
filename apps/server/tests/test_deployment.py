from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.deployment import smoke


def config(uri=None, **kwargs):
    return Settings(_env_file=None, app_env="staging", mongodb_uri=uri, **kwargs)


def test_deployment_rejects_missing_insecure_or_unverified_database():
    for uri in (None, "mongodb://localhost:27017", "mongodb://user:secret@db:27017",
                "mongodb+srv://user:secret@db/?tls=false",
                "mongodb+srv://user:secret@db/?tlsAllowInvalidCertificates=true",
                "mongodb+srv://user:secret@db/?tlsInsecure=true"):
        with pytest.raises(ValidationError) as error:
            config(uri)
        assert "secret" not in str(error.value)
    with pytest.raises(ValidationError):
        config("mongodb+srv://user:secret@db/", enable_kbo_probe=True)
    assert config("mongodb+srv://user:secret@db/").app_env == "staging"
    assert config("mongodb://user:secret@db/?tls=true").app_env == "staging"


def test_smoke_fails_if_readiness_fails_even_when_liveness_passes(monkeypatch):
    real_client = httpx.Client

    def handler(request):
        if request.url.path == "/health/ready":
            return httpx.Response(503, json={"detail": "storage unavailable"})
        return httpx.Response(200, json={"status": "ok"})

    monkeypatch.setattr("app.deployment.httpx.Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(handler)
    ))
    with pytest.raises(httpx.HTTPStatusError):
        smoke("https://staging.example.test", date(2026, 9, 1))


def test_smoke_accepts_empty_games_but_not_invalid_body_or_insecure_remote(monkeypatch):
    real_client = httpx.Client
    game_body = []

    def handler(request):
        assert request.headers["authorization"] == "Bearer test-token"
        if request.url.path == "/v1/games":
            return httpx.Response(200, json=game_body)
        return httpx.Response(200, json={"status": "ok"})

    monkeypatch.setattr("app.deployment.httpx.Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(handler)
    ))
    smoke("https://staging.example.test", date(2026, 9, 1), "test-token")
    game_body = {"error": "not a games list"}
    with pytest.raises(TypeError):
        smoke("https://staging.example.test", date(2026, 9, 1), "test-token")
    with pytest.raises(ValueError):
        smoke("http://remote.example.test", date(2026, 9, 1))
