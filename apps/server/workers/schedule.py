"""Parse bounded public KBO month schedules; never synthesize missing game IDs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from workers.probe_kbo import fetch

SERIES_GROUPS = {"regular": "0,9,6", "postseason": "3,4,5,7"}
# Verified via official /ws/Main.asmx/GetKboGameList in November 2026:
# WC: 20261014OBLG0, 준PO: 20261017LGHT0, PO: 20261026HTSS0, KS: 20261103SSKT0.
POSTSEASON_SERIES = {"WC": "4", "준PO": "3", "PO": "5", "KS": "7"}
GAME_ID = re.compile(r"\d{8}[A-Z]{4}\d")


@dataclass
class ScheduleResult:
    games: list[dict]
    cancelled_without_id: int = 0
    unresolved_without_id: int = 0
    non_game_rows: int = 0


class _Cell(HTMLParser):
    def __init__(self, value: str):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[dict[str, list[str]]] = []
        self.score_parts: list[str] = []
        self.in_score = False
        # The source uses bare &section in href. HTMLParser would decode &sect
        # as the section-sign entity, corrupting both gameId and status.
        value = re.sub(r"&(?!#\d+;|#x[0-9a-fA-F]+;|[A-Za-z][A-Za-z0-9]+;)", "&amp;", value)
        self.feed(value)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(parse_qs(urlparse(attrs["href"]).query))
        if tag == "em":
            self.in_score = True

    def handle_endtag(self, tag):
        if tag == "em":
            self.in_score = False

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)
            if self.in_score:
                self.score_parts.append(text)

    @property
    def text(self):
        return " ".join(self.parts)


def _series(note: str, links: list[dict], series_group: str) -> str:
    explicit = {
        value for link in links for key in ("srId", "seriesId") for value in link.get(key, [])
    }
    if len(explicit) > 1:
        raise ValueError("Conflicting series IDs in schedule row")
    if explicit:
        value = next(iter(explicit))
        if value not in SERIES_GROUPS[series_group].split(","):
            raise ValueError("Unexpected series ID for requested group")
        return value
    if series_group == "postseason":
        prefix = note.split()[0] if note else ""
        if prefix not in POSTSEASON_SERIES:
            raise ValueError("Postseason row has no verified series classification")
        return POSTSEASON_SERIES[prefix]
    # Group includes non-regular special events; do not silently call these series 0.
    if "올스타" in note or "타이브레이크" in note:
        raise ValueError("Special-series row requires explicit series ID verification")
    return "0"


def parse_schedule(payload: str | dict, year: int, series_group: str = "regular") -> ScheduleResult:
    if not isinstance(year, int) or not 1982 <= year <= 2100:
        raise ValueError("Invalid season year")
    if series_group not in SERIES_GROUPS:
        raise ValueError("series_group must be regular or postseason")
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ValueError("Schedule response does not contain rows")  # noqa: TRY004 - source schema
    result = ScheduleResult(games=[])
    seen: dict[str, dict] = {}
    row_date = None
    for row in data["rows"]:
        if not isinstance(row, dict) or not isinstance(row.get("row"), list):
            raise ValueError("Malformed schedule row")  # noqa: TRY004 - source schema
        cells = row["row"]
        if any(
            not isinstance(cell, dict) or not isinstance(cell.get("Text"), str) for cell in cells
        ):
            raise ValueError("Malformed schedule cell")
        for cell in cells:
            if cell.get("Class") == "day":
                match = re.match(r"^(\d{2})\.(\d{2})\(", _Cell(cell["Text"]).text)
                if not match:
                    raise ValueError("Unrecognized schedule date")
                row_date = date(year, int(match[1]), int(match[2]))
        play_cells = [cell for cell in cells if cell.get("Class") == "play"]
        if not play_cells:
            # Source includes blank 이동일/휴식일 rows, which are not missing games.
            visible = " ".join(
                _Cell(cell["Text"]).text for cell in cells if cell.get("Class") != "day"
            ).strip()
            if visible and visible not in {"이동일", "휴식일", "경기가 없습니다."}:
                raise ValueError("Unrecognized non-game schedule row")
            result.non_game_rows += 1
            continue
        if len(play_cells) != 1:
            raise ValueError("Multiple play cells in one schedule row")
        columns = [cell for cell in cells if cell.get("Class") != "day"]
        if len(columns) != 8:
            raise ValueError("Schedule column layout changed")
        parsed = [_Cell(cell["Text"]) for cell in columns]
        note = parsed[-1].text
        cancelled = "취소" in note
        links = [link for cell in parsed for link in cell.links]
        ids = {value for link in links for value in link.get("gameId", [])}
        if not ids:
            if cancelled:
                result.cancelled_without_id += 1
            else:
                result.unresolved_without_id += 1
            continue
        if len(ids) != 1:
            raise ValueError("Conflicting game IDs in schedule row")
        game_id = ids.pop()
        if not GAME_ID.fullmatch(game_id):
            raise ValueError("Invalid source game ID")
        game_date = date(int(game_id[:4]), int(game_id[4:6]), int(game_id[6:8]))
        if game_date.year != year or (row_date is not None and game_date != row_date):
            raise ValueError("Game ID date conflicts with schedule date")
        play = _Cell(play_cells[0]["Text"])
        score = play.score_parts
        away_runs = home_runs = None
        if (
            len(score) == 3
            and score[1].lower() == "vs"
            and score[0].isdigit()
            and score[2].isdigit()
        ):
            away_runs, home_runs = int(score[0]), int(score[2])
        sections = {value.upper() for link in links for value in link.get("section", [])}
        # A score can exist during play. Require the source's REVIEW link as final-state proof.
        status = "unknown"
        if cancelled:
            status = "cancelled"
        elif "REVIEW" in sections and away_runs is not None:
            status = "completed"
        elif sections & {"START_PIT", "PREVIEW"} and away_runs is None:
            status = "scheduled"
        game = {
            "game_id": game_id,
            "game_date": game_date.isoformat(),
            "season": year,
            "series_id": _series(note, links, series_group),
            "away_team_id": game_id[8:10],
            "home_team_id": game_id[10:12],
            "status": status,
            "away_runs": away_runs,
            "home_runs": home_runs,
            "venue": parsed[-2].text or None,
        }
        if game_id in seen and seen[game_id] != game:
            raise ValueError("Conflicting duplicate schedule game")
        seen[game_id] = game
    result.games = sorted(seen.values(), key=lambda item: item["game_id"])
    return result


def fetch_month(year: int, month: int, series_group: str = "regular") -> ScheduleResult:
    """One bounded request per invocation; caller owns rate limiting and season iteration."""
    if not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("month must be 1 through 12")
    # Validate all inputs before doing any network work.
    parse_schedule({"rows": []}, year, series_group)
    payload = fetch(
        "https://www.koreabaseball.com",
        "/ws/Schedule.asmx/GetScheduleList",
        {
            "leId": "1",
            "srIdList": SERIES_GROUPS[series_group],
            "seasonId": str(year),
            "gameMonth": f"{month:02d}",
            "teamId": "",
        },
    )
    return parse_schedule(payload, year, series_group)
