"""Conservative completed-game relay normalizer. Caller must verify finished game status."""

import re
from dataclasses import dataclass, field

from workers.probe_kbo import RelayParser

MARKER = re.compile(r"^(\d+)회(초|말)\s+.+\s+공격\s+-+$")
BATTER = re.compile(r"^\d+번타자 (\S+)$")
RUNNER = re.compile(r"^([123])루주자 (\S+) : (.+)$")
RESULT = re.compile(r"^(\S+) : (.+)$")


@dataclass
class NormalizationResult:
    events: list[dict] = field(default_factory=list)
    complete: bool = False
    reason: str = "unparsed"
    source_counts: dict = field(default_factory=dict)


class UnsupportedRelay(ValueError):
    pass


def _outcome(description):
    if "병살타로 출루" in description:
        return "double_play", 1, 0, "double_play"
    if "병살타 아웃" in description:
        return "double_play", None, 1, "double_play"
    if re.search(r"스트라이크 낫 아웃 \(.+(터치아웃|송구아웃|태그아웃)\)$", description):
        return "strikeout", None, 1, "dropped_third_strike_out"
    if description == "타구맞음 아웃":
        return "out", None, 1, "batter_hit_by_batted_ball"
    if description == "삼진 아웃":
        return "strikeout", None, 1, "strikeout"
    if "아웃" in description and any(x in description for x in (
        "땅볼", "플라이", "라인드라이브", "번트", "직선타"
    )):
        return ("sacrifice" if "희생" in description else "out"), None, 1, "batted_out"
    if description in {"볼넷", "고의4구", "자동 고의4구"}:
        return "walk", 1, 0, "walk"
    if description == "몸에 맞는 볼":
        return "hit_by_pitch", 1, 0, "hit_by_pitch"
    if "홈런" in description:
        return "home_run", 4, 0, "home_run"
    if "실책으로 출루" in description:
        return "error", 1, 0, "reached_on_error"
    if "땅볼로 출루" in description or "야수선택으로 출루" in description:
        return "fielders_choice", 1, 0, "fielders_choice"
    hit = re.search(r"([123])루타$", description)
    if hit:
        return "hit", int(hit[1]), 0, f"hit_{hit[1]}"
    if description.endswith(("내야안타", "번트안타")):
        return "hit", 1, 0, "infield_hit"
    raise UnsupportedRelay("unsupported_batter_result")


def normalize(html, away_team_id, home_team_id, away_runs, home_runs):
    """Return partial diagnostics on failure; consumers MUST NOT publish unless complete=True.

    Half-inning markers delimit reversed blocks in the public HTML. Independent final
    scoreboard totals are required. Names are display text, never stable player IDs.
    """
    relay = RelayParser()
    relay.feed(html)
    result = NormalizationResult(source_counts={"relay_lines": len(relay.lines), "halves": 0})
    if not relay.lines:
        result.reason = "missing_relay"
        return result
    halves = {}
    block = []
    try:
        for line in relay.lines:
            marker = MARKER.fullmatch(line)
            if marker:
                key = (int(marker[1]), 0 if marker[2] == "초" else 1)
                if key in halves:
                    raise UnsupportedRelay("duplicate_half")
                halves[key] = list(reversed(block))
                block = []
            else:
                block.append(line)
        if block:
            raise UnsupportedRelay("unbounded_relay_lines")
        keys = sorted(halves)
        if not keys or keys[0] != (1, 0):
            raise UnsupportedRelay("missing_initial_half")
        expected_keys = [(i // 2 + 1, i % 2) for i in range(len(keys))]
        if keys != expected_keys:
            raise UnsupportedRelay("missing_or_nonsequential_half")
        score = [0, 0]
        def process_half(inning, side, half_index):
            result.source_counts["halves"] += 1
            outs, pa, runner_event = 0, 0, 0
            runners = {}  # name -> base; destination collisions checked after each play
            batter = None
            pending = None
            runner_pending = None
            last_terminal = None
            last_pitch = None
            last_runner_result = None
            half = "top" if side == 0 else "bottom"

            def emit(outcome, before, name, kind, ordinal):
                result.events.append({
                    "event_id": f"{inning}:{half}:{ordinal}",
                    "inning": inning, "half": half,
                    "outs_before": before[0], "runners_before": before[1],
                    "margin_before": before[2],
                    "offense_team_id": away_team_id if side == 0 else home_team_id,
                    "defense_team_id": home_team_id if side == 0 else away_team_id,
                    "outcome": outcome, "batter_name": name, "source_kind": kind,
                })

            def validate_bases():
                if len(set(runners.values())) != len(runners) or len(runners) > 3:
                    raise UnsupportedRelay("runner_destination_collision")
                if outs > 3:
                    raise UnsupportedRelay("too_many_outs")

            def flush():
                nonlocal pending, outs, last_terminal
                if pending is None:
                    return
                outcome, destination, batter_out, kind, before, name = pending
                if destination == 4:
                    score[side] += 1
                elif destination and outs + batter_out < 3:
                    if name in runners:
                        raise UnsupportedRelay("duplicate_batter_runner")
                    runners[name] = destination
                outs += batter_out
                if kind == "fielders_choice" and before[1] == 0:
                    raise UnsupportedRelay("fielders_choice_without_runner")
                if kind == "double_play" and outs - before[0] != 2:
                    raise UnsupportedRelay("double_play_out_count_mismatch")
                validate_bases()
                emit(outcome, before, name, kind, f"pa{pa}")
                last_terminal = (name, outcome, pa)
                pending = None

            def queue_runner(outcome, before, kind):
                nonlocal runner_pending
                if runner_pending is None:
                    runner_pending = (outcome, before, kind)
                elif runner_pending[0] != outcome:
                    flush_runner(validate=False)
                    runner_pending = (outcome, before, kind)

            def flush_runner(validate=True):
                nonlocal runner_pending, runner_event
                if runner_pending is not None:
                    if validate:
                        validate_bases()
                    if runner_pending[0] == "caught_stealing" and outs <= runner_pending[1][0]:
                        raise UnsupportedRelay("caught_stealing_without_out")
                    runner_event += 1
                    outcome, before, kind = runner_pending
                    emit(outcome, before, None, kind, f"runner{runner_event}")
                    runner_pending = None

            for line in halves[(inning, side)]:
                runner = RUNNER.fullmatch(line)
                if runner:
                    base, name, action = int(runner[1]), runner[2], runner[3]
                    action = action.replace("이중도루로 ", "도루로 ")
                    if pending is not None and pending[2] and re.match(
                        r"(도루|폭투|포일|보크)(?:으)?로 ", action
                    ):
                        flush()
                    if outs >= 3 and pending is None:
                        raise UnsupportedRelay("runner_action_after_three_outs")
                    if "대주자" in action and "교체" in action:
                        flush()
                        flush_runner()
                    if pending is not None and name == pending[5] and base == pending[1]:
                        # A new batter-runner can advance again on the same recorded play.
                        if name in runners:
                            raise UnsupportedRelay("duplicate_batter_runner")
                        runners[name] = base
                        pending = (pending[0], None, *pending[2:])
                    if runners.get(name) != base:
                        raise UnsupportedRelay("runner_origin_mismatch")
                    if "대주자" in action and "교체" in action:
                        flush()
                        replacement = re.fullmatch(r"대주자 (\S+) \(으\)로 교체", action)
                        if not replacement:
                            raise UnsupportedRelay("unsupported_runner_substitution")
                        del runners[name]
                        runners[replacement[1]] = base
                        continue
                    # A same-play runner update can temporarily include the batter plus
                    # three old runners. Use the verified pre-play snapshot, not that
                    # transient representation, for separately scored secondary effects.
                    before = pending[4] if pending is not None else (
                        outs, len(runners), score[side] - score[1 - side]
                    )
                    cause_outcomes = {"도루": "stolen_base", "폭투": "wild_pitch",
                                      "포일": "passed_ball", "보크": "balk"}
                    scored_action = action.removeprefix("주자의 재치로 ") if pending is not None else action
                    scored = re.fullmatch(r"(?:(도루|폭투|포일|보크|(?:.+ )?실책)(?:으)?로 )?홈인(?: \(.+\))?", scored_action)
                    if scored:
                        cause = scored[1]
                        if pending is None and cause is None:
                            raise UnsupportedRelay("unattributed_runner_score")
                        del runners[name]
                        score[side] += 1
                        if pending is None:
                            queue_runner(cause_outcomes.get(cause, "error"), before, "runner_score")
                    elif "아웃" in action and any(x in action for x in (
                        "포스아웃", "태그아웃", "도루실패아웃", "견제아웃", "견제사아웃"
                    )):
                        del runners[name]
                        outs += 1
                        last_runner_result = (name, "out", pa, base)
                        if pending is None:
                            queue_runner("caught_stealing" if "도루실패" in action else "out",
                                         before, "runner_out")
                    else:
                        advance = re.fullmatch(
                            r"(?:(도루|폭투|포일|보크|(?:.+ )?실책)(?:으)?로 |다른주자수비하는 사이 |주자의 재치로 |이중도루 실패시 )?"
                            r"([123])루까지 진루(?: \(.+\))?", action
                        )
                        if not advance:
                            raise UnsupportedRelay("unsupported_runner_movement")
                        double_steal_failure = action.startswith("이중도루 실패시 ")
                        if pending is None and advance[1] is None and not double_steal_failure:
                            raise UnsupportedRelay("unattributed_between_pitch_event")
                        runners[name] = int(advance[2])
                        last_runner_result = (name, "safe", pa, int(advance[2]))
                        if double_steal_failure:
                            queue_runner("caught_stealing", before, "double_steal_failure")
                        if advance[1] is not None and not (
                            pending is not None and pending[0] == "error" and "실책" in advance[1]
                        ):
                            queue_runner(cause_outcomes.get(advance[1], "error"), before,
                                         "runner_advance")
                    continue
                flush()
                flush_runner()
                header = BATTER.fullmatch(line)
                if header:
                    if outs >= 3:
                        raise UnsupportedRelay("batter_after_three_outs")
                    pa += 1
                    batter = header[1]
                    last_pitch = None
                    continue
                pitch = re.fullmatch(r"- (\d+)구 (볼|스트라이크|헛스윙|파울|타격|번트파울|번트헛스윙)", line)
                if pitch:
                    last_pitch = (batter, int(pitch[1]), pitch[2], pa)
                    continue
                if re.fullmatch(r"(?:- )?\d+구 피치클락 (투수위반 볼|타자위반 스트라이크)", line):
                    continue
                foul_error = re.fullmatch(r"(?:- )?(\d+)구 (포수|[123]루수|유격수|좌익수|중견수|우익수) 파울 플라이 포구 실책", line)
                if foul_error:
                    if batter is None or outs >= 3:
                        raise UnsupportedRelay("unattributed_foul_error")
                    emit("error", (outs, len(runners), score[side] - score[1 - side]),
                         None, "foul_fly_error", f"pa{pa}-pitch{foul_error[1]}-error")
                    continue
                swing_notice = re.fullmatch(
                    r"(\d+)회([초말]) \d+번타순 (\d+)구 체크스윙 → (노 스윙|스윙) : \S+ (\S+)", line
                )
                if swing_notice:
                    expected_pitch = {"볼"} if swing_notice[4] == "노 스윙" else {"헛스윙", "번트헛스윙"}
                    if not (last_pitch and (int(swing_notice[1]), swing_notice[2]) == (
                        inning, "초" if side == 0 else "말"
                    ) and last_pitch[0] == swing_notice[5] == batter
                        and last_pitch[1] == int(swing_notice[3])
                        and last_pitch[2] in expected_pitch and last_pitch[3] == pa):
                        raise UnsupportedRelay("review_changed_or_unknown")
                    continue
                line_out = re.fullmatch(
                    r"(\d+)회([초말]) \d+번타순 (\d+)구 후 3피트 라인 아웃: \S+ (\S+)", line
                )
                if line_out:
                    matches_terminal = last_terminal is not None and (
                        last_terminal[0] == line_out[4] and last_terminal[2] == pa
                        and last_terminal[1] in {"out", "sacrifice"}
                    )
                    if not (matches_terminal and (int(line_out[1]), line_out[2]) == (
                        inning, "초" if side == 0 else "말"
                    )):
                        raise UnsupportedRelay("unmatched_line_out_notice")
                    if last_pitch != (line_out[4], int(line_out[3]), "타격", pa):
                        raise UnsupportedRelay("unmatched_line_out_notice")
                    continue
                interference_notice = re.fullmatch(
                    r"(\d+)회([초말]) \d+번타순 (\d+)구 후 타자의 포수 수비 방해로 타자 (\S+) 아웃", line
                )
                if interference_notice:
                    if not (last_terminal == (interference_notice[4], "out", pa)
                            and last_pitch == (interference_notice[4], int(interference_notice[3]), "타격", pa)
                            and (int(interference_notice[1]), interference_notice[2]) == (
                                inning, "초" if side == 0 else "말"
                            )):
                        raise UnsupportedRelay("unmatched_interference_out_notice")
                    continue
                if "비디오 판독:" in line:
                    review = re.search(r"판독: (\S+) (.+) 관련 (.+)→(.+)$", line)
                    scope = re.match(r"(\d+)회([초말])", line)
                    if not review or not scope or (int(scope[1]), scope[2]) != (
                        inning, "초" if side == 0 else "말"
                    ):
                        raise UnsupportedRelay("review_changed_or_unknown")
                    if review[3] == review[4]:
                        continue
                    terminal_matches = last_terminal is not None and (
                        last_terminal[0] == review[1] and last_terminal[2] == pa
                    )
                    review_pitch = re.match(r"\d+회[초말] \d+번타순 (\d+)구 후", line)
                    corrected = False
                    if review[2] == "체크스윙" and review_pitch and last_pitch:
                        corrected = last_pitch[0] == review[1] and last_pitch[3] == pa and (
                            last_pitch[1] == int(review_pitch[1])
                        ) and (
                            review[4] == "스윙" and last_pitch[2] in {"헛스윙", "번트헛스윙"}
                            or review[4] == "노 스윙" and last_pitch[2] == "볼"
                        )
                    if not corrected and terminal_matches and review[2] == "체크스윙":
                        corrected = (review[4] == "스윙" and last_terminal[1] == "strikeout") or (
                            review[4] == "노 스윙" and last_terminal[1] == "walk"
                        )
                    elif terminal_matches and review[2] == "타구" and review[4] == "아웃":
                        corrected = last_terminal[1] in {"out", "double_play", "sacrifice"}
                    elif (terminal_matches and review[2] in {"내야타구 페어/파울", "외야타구 페어/파울"}
                          and review[4] == "페어" and review_pitch and last_pitch):
                        corrected = last_terminal[1] in {"hit", "home_run"} and (
                            last_pitch == (review[1], int(review_pitch[1]), "타격", pa)
                        )
                    elif terminal_matches and review[2] in {"타구", "1루 타구"} and review[4] == "세이프":
                        corrected = last_terminal[1] in {"hit", "error", "fielders_choice"} and (
                            review[1] in runners
                            and (review[2] != "1루 타구" or runners[review[1]] == 1)
                        )
                    elif (last_runner_result is not None
                          and last_runner_result[:3] == (review[1], "out", pa)
                          and (re.fullmatch(r"[123]루 도루", review[2]) or (
                              review[2] == "홈 태그" and last_runner_result[3] == 3
                          )) and review[4] == "아웃"):
                        corrected = True
                    elif (last_runner_result is not None
                          and re.fullmatch(r"[123]루 (도루|베이스차단)", review[2])
                          and review[4] == "세이프"):
                        target = int(review[2][0])
                        corrected = last_runner_result == (review[1], "safe", pa, target) and (
                            runners.get(review[1]) == target
                        )
                    if not corrected:
                        raise UnsupportedRelay("review_changed_or_unknown")
                    result.source_counts["confirmed_corrected_reviews"] = (
                        result.source_counts.get("confirmed_corrected_reviews", 0) + 1
                    )
                    continue
                if "교체" in line or "수비위치 변경" in line:
                    # Only explicit substitution statements are inert; a pinch hitter changes the PA name.
                    pinch = re.fullmatch(r"\d+번타자 \S+ : 대타 (\S+) \(으\)로 교체", line)
                    if pinch:
                        batter = pinch[1]
                    elif not re.fullmatch(r"\S+ \S+ : .+ (?:\(으\)로 교체|수비위치 변경)", line):
                        raise UnsupportedRelay("unsupported_substitution")
                    continue
                if re.fullmatch(r"\d+회[초말] \d+번타순 초구 전 \d+분간 폭염 관련 쿨링 브레이크 추가", line):
                    continue
                if re.fullmatch(r"\d+회[초말] \d+번타순 초구 전 ABS 시스템 복구로 해당 투구부터 ABS 재개", line):
                    continue
                if re.fullmatch(r"\d+회[초말] \d+번타순 \d+구 후 \d{2}:\d{2}\s*~\s*\d{2}:\d{2} \(\d+분간\) 우천 관련\(으\)로 경기 중단", line):
                    continue
                if re.fullmatch(r"\d+회[초말] \d+번타순 \d+구 후 [123]루베이스 맞고 (좌중간|우중간|좌익수|중견수|우익수) 방향으로 굴절", line):
                    continue
                if re.fullmatch(r"\d+회[초말] \d+번타순 초구 전 ABS 이슈 해결로 ABS 시스템 경기 진행: \S+ \S+", line):
                    continue
                if re.fullmatch(r"=+", line):
                    continue
                if line in {"투수 투수판 이탈", "타임", "경기종료", "코칭스태프 마운드 방문", "포수 마운드 방문"}:
                    continue
                if re.fullmatch(r"1회초 1번타순 초구 전 .+ 경기개시 지연", line):
                    continue
                if re.fullmatch(r"\d+회[초말] \d+번타순 \d+구 후 (?:헤드샷 관련 퇴장: .+|ABS 추적 실패로 심판 자체 판정: (?:볼|스트라이크)|ABS 시스템 이슈로 해당 투구부터 심판 자체 판정 진행)", line):
                    continue
                if re.fullmatch(r"(무승부투수|패전투수|승리투수|세이브투수|승리팀 홀드투수|패전팀 홀드투수): .+", line):
                    continue
                play = RESULT.fullmatch(line)
                if not play or play[1] != batter or outs >= 3:
                    raise UnsupportedRelay("unknown_impactful_line")
                outcome, destination, batter_out, kind = _outcome(play[2])
                pending = (outcome, destination, batter_out, kind,
                           (outs, len(runners), score[side] - score[1 - side]), batter)
            flush()
            flush_runner()
            is_last = half_index == len(keys) - 1
            walkoff = is_last and inning >= 9 and side == 1 and score[1] > score[0]
            if outs != 3 and not walkoff:
                raise UnsupportedRelay("unclosed_half")
        for half_index, (inning, side) in enumerate(keys):
            process_half(inning, side, half_index)
        if keys[-1][0] < 9:
            raise UnsupportedRelay("shortened_game_requires_separate_verification")
        if keys[-1][1] == 0 and score[1] <= score[0]:
            raise UnsupportedRelay("missing_final_home_half")
        if score[0] == score[1] and "경기종료" not in halves[keys[-1]]:
            raise UnsupportedRelay("tied_game_requires_separate_completion_verification")
        if score != [away_runs, home_runs]:
            raise UnsupportedRelay("final_score_mismatch")
        if len({event["event_id"] for event in result.events}) != len(result.events):
            raise UnsupportedRelay("duplicate_event_id")
        if any(not 0 <= event["outs_before"] <= 2 or not 0 <= event["runners_before"] <= 3
               for event in result.events):
            raise UnsupportedRelay("invalid_event_context")
        result.complete = True
        result.reason = "verified_half_outs_runners_and_final_score"
    except UnsupportedRelay as error:
        result.reason = str(error)
    result.source_counts["normalized_events"] = len(result.events)
    return result
