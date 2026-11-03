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
    dropped = re.fullmatch(r"스트라이크 낫아웃 (포일|폭투)(?:로 출루| 출루)?", description)
    if dropped:
        return ("passed_ball" if dropped[1] == "포일" else "wild_pitch"), 1, 0, "dropped_third_strike_reached"
    if re.fullmatch(r"포수 스트라이크 낫아웃 다른주자 수비로 출루", description):
        return "strikeout_reached", 1, 0, "dropped_third_strike_reached"
    if "삼중살" in description and "아웃" in description:
        return "triple_play", None, 1, "triple_play"
    if re.fullmatch(r"(?:좌익수|중견수|우익수) 희생플라이 \((?:좌익수|중견수|우익수) 실책\)", description):
        return "error", 1, 0, "sacrifice_fly_error"
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
        called_end = False
        def process_half(inning, side, half_index):
            nonlocal called_end
            result.source_counts["halves"] += 1
            outs, pa, runner_event = 0, 0, 0
            runners = {}  # name -> base; destination collisions checked after each play
            batter = None
            pending = None
            runner_pending = None
            last_terminal = None
            last_terminal_kind = None
            last_pitch = None
            last_runner_result = None
            runner_results = {}
            runner_history = {}
            runner_out_actions = {}
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
                nonlocal pending, outs, last_terminal, last_terminal_kind
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
                if kind == "triple_play" and (before[0] != 0 or outs - before[0] != 3):
                    raise UnsupportedRelay("triple_play_out_count_mismatch")
                validate_bases()
                emit(outcome, before, name, kind, f"pa{pa}")
                last_terminal = (name, outcome, pa)
                last_terminal_kind = kind
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

            for line_index, line in enumerate(halves[(inning, side)]):
                runner = RUNNER.fullmatch(line)
                if runner:
                    base, name, action = int(runner[1]), runner[2], runner[3]
                    action = action.replace("이중도루로 ", "도루로 ")
                    failed_steal_error = re.fullmatch(r"도루실패 기록하며 ([123])루까지 진루 \((.+실책.+|.+실책)\)", action)
                    if failed_steal_error:
                        if pending is not None and pending[2]:
                            flush()
                        action = f"실책으로 {failed_steal_error[1]}루까지 진루 ({failed_steal_error[2]})"
                    neutral_advance = action.startswith(("무관심도루로 ", "주루방해로 ")) or (
                        pending is None and action.startswith("주자의 재치로 ")
                    )
                    if neutral_advance:
                        action = re.sub(r"^(무관심도루로 |주루방해로 |주자의 재치로 )", "", action)
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
                    scored_action = action
                    if pending is not None:
                        scored_action = action.removeprefix("주자의 재치로 ").removeprefix("다른주자수비하는 사이 ")
                    scored = re.fullmatch(r"(?:(도루|폭투|포일|보크|(?:.+ )?실책)(?:으)?로 )?홈인(?: \(.+\))?", scored_action)
                    if scored:
                        cause = scored[1]
                        if pending is None and cause is None:
                            raise UnsupportedRelay("unattributed_runner_score")
                        del runners[name]
                        score[side] += 1
                        last_runner_result = (name, "safe", pa, 4)
                        runner_results[name] = last_runner_result
                        if pending is None:
                            queue_runner(cause_outcomes.get(cause, "error"), before, "runner_score")
                    elif "아웃" in action and any(x in action for x in (
                        "포스아웃", "태그아웃", "도루실패아웃", "견제아웃", "견제사아웃", "진루실패아웃", "타구맞음 아웃"
                    )):
                        del runners[name]
                        outs += 1
                        last_runner_result = (name, "out", pa, base)
                        runner_results[name] = last_runner_result
                        runner_out_actions[name] = action
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
                        if pending is None and advance[1] is None and not double_steal_failure and not neutral_advance:
                            raise UnsupportedRelay("unattributed_between_pitch_event")
                        runners[name] = int(advance[2])
                        last_runner_result = (name, "safe", pa, int(advance[2]))
                        runner_results[name] = last_runner_result
                        runner_history.setdefault(name, set()).add(int(advance[2]))
                        if neutral_advance:
                            queue_runner("runner_advance", before, "explicit_neutral_advance")
                        if double_steal_failure:
                            queue_runner("caught_stealing", before, "double_steal_failure")
                        if advance[1] is not None and not (
                            pending is not None and (
                                pending[0] == "error" and "실책" in advance[1]
                                or pending[0] == cause_outcomes.get(advance[1])
                            )
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
                    runner_results.clear()
                    runner_history.clear()
                    runner_out_actions.clear()
                    continue
                pitch = re.fullmatch(r"- (\d+)구 (볼|스트라이크|헛스윙|파울|타격|번트파울|번트헛스윙)", line)
                if pitch:
                    last_pitch = (batter, int(pitch[1]), pitch[2], pa)
                    continue
                if re.fullmatch(r"(?:- )?\d+구 피치클락 (투수위반 볼|타자위반 스트라이크)", line):
                    continue
                foul_error = re.fullmatch(r"(?:- )?(\d+)구 (투수|포수|[123]루수|유격수|좌익수|중견수|우익수) 파울 플라이 포구 실책", line)
                if foul_error:
                    if (batter is None or outs >= 3 or last_pitch is None
                            or last_pitch != (batter, int(foul_error[1]), "파울", pa)):
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
                        following = halves[(inning, side)][line_index + 1:line_index + 2]
                        superseding = re.fullmatch(
                            rf"{inning}회{'초' if side == 0 else '말'} \d+번타순 {swing_notice[3]}구 후 .+비디오 판독: "
                            rf"{re.escape(swing_notice[5])} 체크스윙 관련 노 스윙→스윙", following[0]
                        ) if following else None
                        if not (superseding and swing_notice[4] == "노 스윙" and last_pitch
                                and last_pitch[0] == swing_notice[5] == batter
                                and last_pitch[1] == int(swing_notice[3]) and last_pitch[3] == pa
                                and last_pitch[2] in {"헛스윙", "번트헛스윙"}):
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
                bat_interference = re.fullmatch(
                    r"(\d+)회([초말]) \d+번타순 (\d+)구 후 타격 후 타자가 떨어뜨린 배트에 공이 닿아 수비방해 아웃 선언: \S+ (\S+)", line
                )
                if bat_interference:
                    if not (last_terminal == (bat_interference[4], "out", pa)
                            and last_pitch == (bat_interference[4], int(bat_interference[3]), "타격", pa)
                            and (int(bat_interference[1]), bat_interference[2]) == (
                                inning, "초" if side == 0 else "말"
                            )):
                        raise UnsupportedRelay("unmatched_interference_out_notice")
                    continue
                if "비디오 판독:" in line:
                    review = re.search(r"판독: (\S+) (.+) 관련(?:\(파울팁\))? (.+)→(.+)$", line)
                    scope = re.match(r"(\d+)회([초말])", line)
                    if not review or not scope or (int(scope[1]), scope[2]) != (
                        inning, "초" if side == 0 else "말"
                    ):
                        raise UnsupportedRelay("review_changed_or_unknown")
                    if review[3] == review[4]:
                        continue
                    last_runner_result = runner_results.get(review[1])
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
                    elif terminal_matches and review[2] in {"타구", "1루 타구"} and review[4] == "아웃":
                        corrected = last_terminal[1] in {"out", "double_play", "sacrifice"}
                    elif (terminal_matches and review[2] in {"내야타구 페어/파울", "외야타구 페어/파울"}
                          and review[4] == "페어" and review_pitch and last_pitch):
                        corrected = last_terminal[1] in {"hit", "home_run"} and (
                            last_pitch == (review[1], int(review_pitch[1]), "타격", pa)
                        )
                    elif (review[2] in {"내야타구 페어/파울", "외야타구 페어/파울"}
                          and review[4] == "파울" and review_pitch and last_pitch):
                        corrected = last_pitch == (review[1], int(review_pitch[1]), "파울", pa)
                    elif terminal_matches and review[2] in {"타구", "1루 타구"} and review[4] == "세이프":
                        corrected = last_terminal[1] in {"hit", "error", "fielders_choice"} and (
                            review[1] in runners
                            and (review[2] != "1루 타구" or runners[review[1]] == 1)
                        )
                    elif (last_runner_result is not None
                          and last_runner_result[:3] == (review[1], "out", pa)
                          and (re.fullmatch(r"[123]루 도루", review[2]) or review[2] in {"견제", "1루 견제", "2루 견제", "3루 견제"} or (
                              review[2] == "홈 태그" and last_runner_result[3] == 3
                          )) and review[4] == "아웃"):
                        corrected = True
                    elif (last_runner_result is not None
                          and re.fullmatch(r"[123]루 (도루|베이스차단|태그)", review[2])
                          and review[4] == "세이프"):
                        target = int(review[2][0])
                        corrected = last_runner_result == (review[1], "safe", pa, target) and (
                            runners.get(review[1]) == target
                        )
                    elif (last_runner_result is not None and review[2] == "베이스터치"
                          and review[4] == "세이프"):
                        corrected = last_runner_result[:3] == (review[1], "safe", pa) and (
                            runners.get(review[1]) == last_runner_result[3]
                        )
                    elif review[2] in {"홈 태그", "홈 타구"} and review[4] == "세이프":
                        corrected = last_runner_result == (review[1], "safe", pa, 4)
                    elif (re.fullmatch(r"[123]루 포스아웃", review[2]) and review[4] == "세이프"
                          and review_pitch and last_pitch and last_pitch[3] == pa
                          and last_pitch[1] == int(review_pitch[1])):
                        corrected = int(review[2][0]) in runner_history.get(review[1], set())
                    elif (re.fullmatch(r"[123]루 태그", review[2]) and review[4] == "아웃"
                          and review_pitch and last_pitch and last_pitch[3] == pa
                          and last_pitch[1] == int(review_pitch[1])):
                        corrected = last_runner_result is not None and (
                            last_runner_result[:3] == (review[1], "out", pa)
                            and review[1] not in runners
                            and any(word in runner_out_actions.get(review[1], "") for word in (
                                "태그아웃", "도루실패아웃", "진루실패아웃"
                            ))
                        )
                    same_pitch = review_pitch is not None and last_pitch is not None and (
                        last_pitch[1] == int(review_pitch[1]) and last_pitch[3] == pa
                    )
                    if not corrected and same_pitch:
                        subject, category, after = review[1], review[2], review[4]
                        category = {"몸에 맞는 공": "몸에맞는공", "홈런성 타구": "홈런성타구"}.get(category, category)
                        if category in {"몸에맞는공", "파울/스윙", "포구", "홈런성타구"}:
                            expected = {"파울": {"파울"}, "스윙": {"헛스윙", "번트헛스윙"}}
                            if after in expected:
                                corrected = last_pitch[0] == subject and last_pitch[2] in expected[after]
                            elif terminal_matches and after == "사구" and category == "몸에맞는공":
                                corrected = last_terminal[1] == "hit_by_pitch"
                            elif terminal_matches and category == "홈런성타구":
                                corrected = (after == "홈런" and last_terminal[1] == "home_run") or (
                                    after == "2루타" and last_terminal_kind == "hit_2"
                                )
                        safe_terminal_categories = {
                            "포구": None, "1루 포스아웃": 1, "1루 태그": 1,
                            "2루 태그": 2, "3루 타구": 3,
                        }
                        if terminal_matches and after == "세이프" and category in safe_terminal_categories:
                            base = safe_terminal_categories[category]
                            corrected = last_terminal[1] in {"hit", "error", "fielders_choice"} and (
                                base is None or runners.get(subject) == base
                            )
                        if terminal_matches and after == "아웃" and category in {"1루 포스아웃", "1루 베이스터치"}:
                            corrected = last_terminal[1] in {"out", "double_play", "sacrifice", "triple_play"}
                        if (after == "아웃" and last_runner_result is not None
                                and last_runner_result[:3] == (subject, "out", pa)
                                and subject not in runners):
                            action = runner_out_actions.get(subject, "")
                            if category in {"홈 포스아웃", "2루 포스아웃"}:
                                corrected = "포스아웃" in action
                            elif category in {"베이스차단", "태그", "도루", "3루 베이스터치", "2루 베이스터치", "홈 타구"}:
                                corrected = any(word in action for word in ("태그아웃", "도루실패아웃", "포스아웃"))
                    if not corrected:
                        raise UnsupportedRelay("review_changed_or_unknown")
                    result.source_counts["confirmed_corrected_reviews"] = (
                        result.source_counts.get("confirmed_corrected_reviews", 0) + 1
                    )
                    continue
                if re.fullmatch(
                    r"\d+회[초말] \d+번타순 (?:초구 전|\d+구 후) "
                    r"(?:\d{2}:\d{2}\s*~\s*\d{2}:\d{2} \(\d+분간\) )?"
                    r"\S+ 대기심이 (?:주심|[123]루심)\(으\)로 교체", line
                ):
                    continue
                rule_note = re.fullmatch(r"(\d+)회([초말]) \d+번타순 (\d+)구 후 (.+)", line)
                if rule_note and last_pitch and (
                    (int(rule_note[1]), rule_note[2]) == (inning, "초" if side == 0 else "말")
                    and last_pitch[1] == int(rule_note[3]) and last_pitch[3] == pa
                ):
                    body = rule_note[4]
                    runner_note = re.fullmatch(
                        r"(?:3루 주루코치와의 접촉으로 아웃 선언: \S+ |3피트 라인 이탈 아웃: \S+ |"
                        r"[123]루주자의 \S+ 수비 방해로 [123]루주자 |타자의 포수 수비 방해로 [123]루주자 )(\S+) 아웃", body
                    )
                    # Two source variants end with the name, rather than repeating 'out'.
                    named_runner = re.fullmatch(r"(?:3루 주루코치와의 접촉으로 아웃 선언:|3피트 라인 이탈 아웃:) \S+ (\S+)", body)
                    trailing_runner = re.fullmatch(r"[123]루주자 (\S+) 3피트라인 아웃 선언", body)
                    coach_runner = re.fullmatch(r"[123]루주자 (\S+) 베이스 코치와 접촉으로 아웃: \S+ (\S+)", body)
                    if coach_runner and coach_runner[1] != coach_runner[2]:
                        raise UnsupportedRelay("contradictory_runner_notice")
                    candidate = runner_note or named_runner or trailing_runner or coach_runner
                    if candidate and runner_results.get(candidate[1], ())[:3] == (candidate[1], "out", pa):
                        continue
                    batter_note = re.fullmatch(
                        r"(?:대기타자 \S+의 \S+ 수비방해로 타자 (\S+) 아웃|페어타구 배트에 닿아 아웃: \S+ (\S+))", body
                    )
                    if batter_note:
                        name = batter_note[1] or batter_note[2]
                        if last_terminal == (name, "out", pa) and last_pitch[0] == name:
                            continue
                    hit_note = re.fullmatch(
                        r"(?:타구가? [123]루 베이스 맞고 굴절 ?(?:되었음|됨)|내야 타구 [123]루심 맞아 안타: \S+ (\S+)|타구가 천장에 맞음: \S+ (\S+))", body
                    )
                    if hit_note and last_terminal == (batter, "hit", pa) and last_pitch[0] == batter:
                        named = hit_note[1] or hit_note[2]
                        if named is None or named == batter:
                            continue
                    if (body in {"최초 직선타 형태, 병살타 인정 안됨(9.02(a)(17))", "고의낙구 선언"}
                            and last_terminal == (batter, "out", pa) and last_pitch[0] == batter):
                        continue
                if re.fullmatch(
                    r"\d+회[초말] \d+번타순 초구 전 방송사 중계시스템 오류로 인하여 비디오판독 불가한 상태로 경기진행\(\d+회[초말] \d+번타순 \d+구후 복구\)", line
                ):
                    continue
                if re.fullmatch(
                    r"1회초 1번타순 초구 전 폭염으로 경기 개시 \d+분 지연 \(\d+시 \d+분 개시 예정\)", line
                ) and inning == 1 and side == 0 and outs == 0 and not result.events:
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
                if re.fullmatch(
                    r"\d+회[초말] \d+번타순 (?:초구 전|\d+구 후) (?:"
                    r"(?:\d+분간 )?(?:폭염 관련|그라운드 정비관련) (?:클리닝 타임|쿨링 브레이크) 추가(?:\(으\)로 경기 중단)?|"
                    r"ABS 시스템 (?:복구 완료|복구로 해당 투구부터 ABS 재개|이슈로 해당 투구부터 심판 자체 판정 진행)|"
                    r"\d{2}:\d{2}(?:\s*~\s*\d{2}:\d{2} \(\d+분간\))? (?:우천 관련|클리닝 타임 불꽃 놀이 행사 여파)\(으\)로 경기 중단)", line
                ):
                    continue
                if re.fullmatch(r"데일리 MVP \S+ \S+(?: / 시리즈 MVP \S+ \S+)?", line) and (
                    half_index == len(keys) - 1 and "경기종료" in halves[(inning, side)]
                ):
                    continue
                administrative = re.fullmatch(
                    r"\d+회[초말] \d+번타순 (?:초구 전|\d+구 후) "
                    r"(?:\d{2}:\d{2}(?:\s*~\s*\d{2}:\d{2})?(?: \(\d+분간\))? )?"
                    r"(?:"
                    r"(?:부상 관련|항의 관련|우천/그라운드 정비|경기장 외부 화재로 인한 연기발생|관중 응급상황|"
                    r"벤치클리어링 관련|관중석 응급환자 발생|야구장 인근 콘서트 행사로 인한 불꽃 연기)\(으\)로 경기 중단|"
                    r"(?:헤드샷 관련|비디오판독 판정 항의 관련) 퇴장: \S+ \S+(?: 감독)?|"
                    r"(?:와인드업 투구 자세에서 자유족을 뺀 이후 투수판 이탈|빈볼성 투구 관련) 경고: \S+ \S+)", line
                )
                if administrative:
                    continue
                called_notice = re.fullmatch(
                    r"(\d+)회([초말]) \d+번타순 (?:초구 전|\d+구 후) (?:\d{2}:\d{2} )?강우 콜드게임 선언", line
                )
                if called_notice:
                    if not (half_index == len(keys) - 1 and inning >= 5 and (
                        int(called_notice[1]), called_notice[2]
                    ) == (inning, "초" if side == 0 else "말")):
                        raise UnsupportedRelay("unverified_called_game_end")
                    called_end = True
                    continue
                if re.fullmatch(r"=+", line):
                    continue
                if line in {"투수 투수판 이탈", "타임", "경기종료", "코칭스태프 마운드 방문", "포수 마운드 방문", "포수 덕아웃 방문"}:
                    continue
                if re.fullmatch(r"1회초 1번타순 초구 전 .+ 경기개시 지연", line):
                    continue
                if re.fullmatch(r"\d+회[초말] \d+번타순 \d+구 후 (?:헤드샷 관련 퇴장: .+|ABS 추적 실패로 심판 자체 판정: (?:볼|스트라이크)|ABS 시스템 이슈로 해당 투구부터 심판 자체 판정 진행)", line):
                    continue
                if re.fullmatch(r"(무승부팀 홀드투수|무승부투수|패전투수|승리투수|세이브투수|승리팀 홀드투수|패전팀 홀드투수): .+", line):
                    continue
                play = RESULT.fullmatch(line)
                if not play or play[1] != batter or outs >= 3:
                    raise UnsupportedRelay("unknown_impactful_line")
                outcome, destination, batter_out, kind = _outcome(play[2])
                if kind == "dropped_third_strike_reached" and outs < 2 and 1 in runners.values():
                    raise UnsupportedRelay("ineligible_dropped_third_strike_reach")
                pending = (outcome, destination, batter_out, kind,
                           (outs, len(runners), score[side] - score[1 - side]), batter)
            flush()
            flush_runner()
            is_last = half_index == len(keys) - 1
            walkoff = is_last and inning >= 9 and side == 1 and score[1] > score[0]
            if outs != 3 and not walkoff and not (is_last and called_end):
                raise UnsupportedRelay("unclosed_half")
        for half_index, (inning, side) in enumerate(keys):
            process_half(inning, side, half_index)
        if keys[-1][0] < 9 and not called_end:
            raise UnsupportedRelay("shortened_game_requires_separate_verification")
        if keys[-1][1] == 0 and score[1] <= score[0] and not called_end:
            raise UnsupportedRelay("missing_final_home_half")
        if score[0] == score[1] and "경기종료" not in halves[keys[-1]] and not called_end:
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
