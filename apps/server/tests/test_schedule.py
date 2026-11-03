import json

import pytest

from workers.schedule import fetch_month, parse_schedule


def cell(text, cls=None):
    return {"Text": text, "Class": cls}


def row(game_id="20260901LGOB0", section="REVIEW", runs=(3, 1), note="-", day="09.01(화)"):
    score = (
        "<span>vs</span>"
        if runs is None
        else f"<span>{runs[0]}</span><span>vs</span><span>{runs[1]}</span>"
    )
    link = (
        f'<a href="/Schedule/GameCenter/Main.aspx?gameId={game_id}&amp;section={section}">상세</a>'
        if game_id
        else ""
    )
    cells = [
        cell("18:30", "time"),
        cell(f"<span>LG</span><em>{score}</em><span>두산</span>", "play"),
        cell(link, "relay"),
        cell(""),
        cell("TV"),
        cell(""),
        cell("잠실"),
        cell(note),
    ]
    return {"row": ([cell(day, "day")] if day else []) + cells}


def test_review_proves_completion_and_scores_alone_do_not():
    completed = parse_schedule({"rows": [row()]}, 2026)
    assert completed.games == [
        {
            "game_id": "20260901LGOB0",
            "game_date": "2026-09-01",
            "season": 2026,
            "series_id": "0",
            "away_team_id": "LG",
            "home_team_id": "OB",
            "status": "completed",
            "away_runs": 3,
            "home_runs": 1,
            "venue": "잠실",
        }
    ]
    assert parse_schedule({"rows": [row(section="LIVE")]}, 2026).games[0]["status"] == "unknown"
    assert (
        parse_schedule({"rows": [row(section="START_PIT", runs=None)]}, 2026).games[0]["status"]
        == "scheduled"
    )
    assert parse_schedule({"rows": [row(runs=None)]}, 2026).games[0]["status"] == "unknown"


def test_missing_ids_are_counted_not_synthesized_and_rest_rows_are_separate():
    rest = {"row": [cell("09.02(수)", "day")] + [cell("")] * 7 + [cell("이동일")]}
    result = parse_schedule(
        {
            "rows": [
                row(game_id=None, note="우천취소", runs=None),
                row(game_id=None, runs=None),
                rest,
            ]
        },
        2026,
    )
    assert result.games == []
    assert result.cancelled_without_id == 1
    assert result.unresolved_without_id == 1
    assert result.non_game_rows == 1


def test_rowspan_doubleheader_ids_and_ties_are_preserved():
    result = parse_schedule(
        {
            "rows": [
                row(game_id="20260901LGOB1", runs=(0, 0)),
                row(game_id="20260901LGOB2", day=None),
            ]
        },
        2026,
    )
    assert [g["game_id"] for g in result.games] == ["20260901LGOB1", "20260901LGOB2"]
    assert result.games[0]["status"] == "completed"
    assert result.games[0]["away_runs"] == 0


@pytest.mark.parametrize("prefix,series", [("WC", "4"), ("준PO", "3"), ("PO", "5"), ("KS", "7")])
def test_verified_postseason_mapping(prefix, series):
    result = parse_schedule({"rows": [row(note=f"{prefix} 1차전")]}, 2026, "postseason")
    assert result.games[0]["series_id"] == series


def test_errors_do_not_become_empty_success_or_synthetic_records():
    for payload in ["<html>Error</html>", {}, {"rows": [{}]}]:
        with pytest.raises(ValueError):
            parse_schedule(payload, 2026)
    with pytest.raises(ValueError, match="date conflicts"):
        parse_schedule({"rows": [row(game_id="20260902LGOB0")]}, 2026)
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        parse_schedule({"rows": [row(), row(runs=(4, 1))]}, 2026)
    with pytest.raises(ValueError, match="classification"):
        parse_schedule({"rows": [row(note="미분류")]}, 2026, "postseason")
    with pytest.raises(ValueError, match="Special-series"):
        parse_schedule({"rows": [row(note="올스타전")]}, 2026)
    assert len(parse_schedule({"rows": [row(), row()]}, 2026).games) == 1


def test_fetch_month_is_exactly_one_request_and_validates_before_network(monkeypatch):
    calls = []

    def fake_fetch(base, path, params):
        calls.append((base, path, params))
        return json.dumps({"rows": [row()]})

    monkeypatch.setattr("workers.schedule.fetch", fake_fetch)
    assert len(fetch_month(2026, 9).games) == 1
    assert calls == [
        (
            "https://www.koreabaseball.com",
            "/ws/Schedule.asmx/GetScheduleList",
            {"leId": "1", "srIdList": "0,9,6", "seasonId": "2026", "gameMonth": "09", "teamId": ""},
        )
    ]
    for args in [(2026, 13, "regular"), (2026, 9, "invalid"), (0, 9, "regular")]:
        with pytest.raises(ValueError):
            fetch_month(*args)
    assert len(calls) == 1


def test_source_bare_ampersand_section_query_is_not_html_entity():
    source_row = row()
    for item in source_row["row"]:
        item["Text"] = item["Text"].replace("&amp;section=", "&section=")
    result = parse_schedule({"rows": [source_row]}, 2026)
    assert result.games[0]["game_id"] == "20260901LGOB0"
    assert result.games[0]["status"] == "completed"


@pytest.mark.parametrize("group", ["regular", "postseason"])
@pytest.mark.parametrize("key", ["srId", "seriesId"])
def test_preseason_source_category_is_rejected_even_during_regular_dates(group, key):
    source_row = row()
    for item in source_row["row"]:
        item["Text"] = item["Text"].replace("&amp;section=", f"&amp;{key}=1&amp;section=")
    with pytest.raises(ValueError, match="Unexpected series ID"):
        parse_schedule({"rows": [source_row]}, 2026, group)
