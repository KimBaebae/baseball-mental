"""Synthetic local cache checks; no network or third-party source fixtures."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from workers import backfill


def sample():
    return SimpleNamespace(game_id="20260901LGOB0", series_id="0")


def test_cache_hit_and_refresh_have_explicit_fetch_semantics(tmp_path, monkeypatch):
    calls = []

    def fetch(*args):
        calls.append(args)
        return f"synthetic source {len(calls)}"

    monkeypatch.setattr(backfill, "fetch", fetch)
    directory = backfill.prepare_relay_cache(tmp_path / "private-relays")
    first = backfill.load_relay(sample(), directory)
    assert backfill.load_relay(sample(), directory) == first
    assert len(calls) == 1
    assert backfill.load_relay(sample(), directory, refresh=True) == "synthetic source 2"
    assert backfill.load_relay(sample(), directory) == "synthetic source 2"
    assert len(calls) == 2
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / f"{sample().game_id}.html").stat().st_mode & 0o777 == 0o600


def test_repository_cache_is_rejected_before_directory_creation(tmp_path):
    with pytest.raises(ValueError, match="outside any Git"):
        backfill.prepare_relay_cache(Path(backfill.__file__).parent / "raw-cache")
    other_repo = tmp_path / "other-repo"
    other_repo.mkdir()
    (other_repo / ".git").write_text("gitdir: elsewhere")
    with pytest.raises(ValueError, match="outside any Git"):
        backfill.prepare_relay_cache(other_repo / "cache")
    assert not (other_repo / "cache").exists()


def test_cache_limit_and_symlink_are_rejected(tmp_path, monkeypatch):
    directory = backfill.prepare_relay_cache(tmp_path / "cache")
    target = directory / f"{sample().game_id}.html"
    target.write_bytes(b"x" * (backfill.MAX_RELAY_BYTES + 1))
    with pytest.raises(ValueError, match="size limit"):
        backfill.load_relay(sample(), directory)
    target.unlink()
    other = tmp_path / "outside"
    other.write_text("synthetic")
    target.symlink_to(other)
    with pytest.raises(ValueError, match="symlinks"):
        backfill.load_relay(sample(), directory, refresh=True)


def test_existing_shared_directory_is_rejected_without_changing_permissions(tmp_path):
    directory = tmp_path / "shared"
    directory.mkdir()
    directory.chmod(0o755)
    with pytest.raises(ValueError, match="must be private"):
        backfill.prepare_relay_cache(directory)
    assert directory.stat().st_mode & 0o777 == 0o755
