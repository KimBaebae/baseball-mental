"""Synthetic baseball scenarios; these are not copied source games or validation evidence."""

from html import escape

from workers.normalize import normalize


def three_outs():
    return [line for n in range(1, 4) for line in (
        f"{n}번타자 가상타자{n}", "- 1구 타격", f"가상타자{n} : 중견수 플라이 아웃"
    )]


def source(overrides=None, omitted=None):
    overrides = overrides or {}
    parts = []
    for inning in range(1, 10):
        for side in (1, 0):  # Source groups are bottom first, internally reverse chronology.
            if (inning, side) == omitted:
                continue
            lines = three_outs()
            if (inning, side) == (1, 0):
                lines = ["4번타자 가상홈런", "가상홈런 : 좌중간 뒤 홈런 (홈런거리:100M)"] + lines
            lines = overrides.get((inning, side), lines)
            for line in reversed(lines):
                parts.append(f'<span id="spanLiveText_{len(parts)}">{escape(line)}</span>')
            marker = f"{inning}회{'초' if side == 0 else '말'} 가상팀 공격 -------"
            parts.append(f'<span id="spanLiveText_{len(parts)}">{marker}</span>')
    return "".join(parts)


def test_orders_source_and_verifies_full_score_outs_and_empty_initial_bases():
    result = normalize(source(), "AA", "BB", 1, 0)
    assert result.complete
    assert len(result.events) == 55
    first, second = result.events[:2]
    assert first["outcome"] == "home_run"
    assert (first["inning"], first["half"], first["outs_before"],
            first["runners_before"], first["margin_before"]) == (1, "top", 0, 0, 0)
    assert second["margin_before"] == 1
    bottom = next(event for event in result.events if event["half"] == "bottom")
    assert bottom["margin_before"] == -1
    assert len({event["event_id"] for event in result.events}) == len(result.events)


def test_pitch_runner_event_updates_next_play_context_without_batter_attribution():
    lines = ["4번타자 가상주자", "가상주자 : 볼넷", "5번타자 가상타자",
             "- 1구 볼", "1루주자 가상주자 : 폭투로 2루까지 진루",
             "가상타자 : 우익수 오른쪽 2루타", "2루주자 가상주자 : 홈인"] + three_outs()
    result = normalize(source({(1, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    walk, wild_pitch, hit = result.events[:3]
    assert walk["outcome"] == "walk"
    assert wild_pitch["outcome"] == "wild_pitch"
    assert wild_pitch["batter_name"] is None
    assert hit["runners_before"] == 1
    assert hit["margin_before"] == 0
    assert result.events[3]["margin_before"] == 1


def test_double_play_counts_explicit_runner_out_once():
    lines = ["4번타자 가상주자", "가상주자 : 볼넷", "5번타자 가상타자",
             "가상타자 : 유격수 병살타 아웃 (유격수->2루수->1루수 송구아웃)",
             "1루주자 가상주자 : 포스아웃 (유격수->2루수 2루 터치아웃)",
             "6번타자 가상마지막", "가상마지막 : 삼진 아웃"]
    result = normalize(source({(2, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    plays = [e for e in result.events if e["inning"] == 2 and e["half"] == "top"]
    assert plays[1]["outcome"] == "double_play"
    assert plays[1]["outs_before"] == 0
    assert plays[2]["outs_before"] == 2
    incomplete = normalize(source({(2, 0): [l for l in lines if not l.startswith("1루주자")]}),
                           "AA", "BB", 1, 0)
    assert not incomplete.complete
    assert incomplete.reason == "double_play_out_count_mismatch"


def test_missing_half_final_score_mismatch_and_unknown_line_never_publish():
    missing = normalize(source(omitted=(3, 0)), "AA", "BB", 1, 0)
    assert not missing.complete and missing.reason == "missing_or_nonsequential_half"
    wrong_score = normalize(source(), "AA", "BB", 2, 0)
    assert not wrong_score.complete and wrong_score.reason == "final_score_mismatch"
    unknown = normalize(source({(4, 0): ["알 수 없는 경기 사건"] + three_outs()}), "AA", "BB", 1, 0)
    assert not unknown.complete and unknown.reason == "unknown_impactful_line"


def test_overturned_review_is_incomplete_even_if_final_score_matches():
    lines = ["3회초 1번타순 1구 후 비디오 판독: 가상타자 타구 관련 세이프→아웃"] + three_outs()
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert not result.complete and result.reason == "review_changed_or_unknown"


def test_runner_origin_mismatch_and_unclosed_half_are_incomplete():
    bad_runner = normalize(source({(3, 0): ["1루주자 없는주자 : 도루로 2루까지 진루"]}),
                           "AA", "BB", 1, 0)
    assert not bad_runner.complete and bad_runner.reason == "runner_origin_mismatch"
    unfinished = normalize(source({(3, 0): three_outs()[:-3]}), "AA", "BB", 1, 0)
    assert not unfinished.complete and unfinished.reason == "unclosed_half"


def test_third_out_fielders_choice_does_not_require_unrecorded_runner_advance():
    lines = three_outs()[:6] + [
        "4번타자 가상둘째", "가상둘째 : 중견수 오른쪽 2루타",
        "5번타자 가상첫째", "가상첫째 : 볼넷",
        "6번타자 가상타자", "가상타자 : 3루수 앞 땅볼로 출루",
        "2루주자 가상둘째 : 포스아웃 (3루수 3루 터치아웃)",
    ]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    play = next(e for e in result.events if e["outcome"] == "fielders_choice")
    assert play["outs_before"] == 2 and play["runners_before"] == 2


def test_hit_by_pitch_and_sacrifice_keep_distinct_outcomes():
    lines = ["4번타자 가상주자", "가상주자 : 몸에 맞는 볼", "5번타자 가상타자",
             "가상타자 : 투수 희생번트 아웃 (투수->1루수 송구아웃)",
             "1루주자 가상주자 : 2루까지 진루"] + three_outs()[:6]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    plays = [e for e in result.events if e["inning"] == 3 and e["half"] == "top"]
    assert [e["outcome"] for e in plays[:2]] == ["hit_by_pitch", "sacrifice"]


def test_multi_runner_wild_pitch_is_one_event_with_pre_pitch_context():
    lines = [
        "4번타자 가상둘째", "가상둘째 : 중견수 오른쪽 2루타",
        "5번타자 가상첫째", "가상첫째 : 볼넷", "6번타자 가상타자", "- 1구 볼",
        "1루주자 가상첫째 : 폭투로 2루까지 진루",
        "2루주자 가상둘째 : 폭투로 3루까지 진루",
        "가상타자 : 삼진 아웃",
    ] + three_outs()[:6]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    pitches = [e for e in result.events if e["outcome"] == "wild_pitch"]
    assert len(pitches) == 1
    assert pitches[0]["runners_before"] == 2
    assert pitches[0]["outs_before"] == 0


def test_corrected_swing_review_requires_matching_terminal_batter_outcome():
    review = "3회초 1번타순 1구 후 비디오 판독: 가상타자1 체크스윙 관련 노 스윙→스윙"
    lines = ["1번타자 가상타자1", "- 1구 헛스윙", "가상타자1 : 삼진 아웃", review] + three_outs()[3:]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    assert result.source_counts["confirmed_corrected_reviews"] == 1
    wrong = normalize(source({(3, 0): [line.replace("가상타자1 체크", "다른이름 체크")
                                      for line in lines]}), "AA", "BB", 1, 0)
    assert not wrong.complete and wrong.reason == "review_changed_or_unknown"


def test_same_play_batter_runner_extra_advance_and_explicit_error():
    lines = [
        "4번타자 가상주자", "가상주자 : 좌익수 왼쪽 1루타",
        "1루주자 가상주자 : 실책으로 2루까지 진루",
    ] + three_outs()
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    plays = [e for e in result.events if e["inning"] == 3 and e["half"] == "top"]
    assert [e["outcome"] for e in plays[:2]] == ["hit", "error"]
    assert plays[2]["runners_before"] == 1


def test_stolen_base_then_throwing_error_are_two_distinct_actions():
    lines = [
        "4번타자 가상주자", "가상주자 : 볼넷", "5번타자 가상타자", "- 1구 볼",
        "1루주자 가상주자 : 도루로 2루까지 진루",
        "2루주자 가상주자 : 포수 실책으로 3루까지 진루 (포수 송구 실책)",
        "가상타자 : 삼진 아웃",
    ] + three_outs()[:6]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    plays = [e for e in result.events if e["inning"] == 3 and e["half"] == "top"]
    assert [e["outcome"] for e in plays[:3]] == ["walk", "stolen_base", "error"]


def test_runner_score_without_batter_is_explicit_passed_ball():
    lines = [
        "4번타자 가상주자", "가상주자 : 우익수 오른쪽 3루타", "5번타자 가상타자", "- 1구 볼",
        "3루주자 가상주자 : 포일로 홈인", "가상타자 : 삼진 아웃",
    ] + three_outs()[:6]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 2, 0)
    assert result.complete
    passed = next(e for e in result.events if e["outcome"] == "passed_ball")
    assert passed["batter_name"] is None and passed["margin_before"] == 1


def test_no_original_marker_or_tied_game_never_claims_complete():
    assert not normalize("<p>no relay</p>", "AA", "BB", 0, 0).complete
    tied = normalize(source({(1, 0): three_outs()}), "AA", "BB", 0, 0)
    assert not tied.complete
    assert tied.reason == "tied_game_requires_separate_completion_verification"


def test_steal_after_strikeout_uses_post_strikeout_outs():
    lines = [
        "4번타자 가상주자", "가상주자 : 볼넷", "5번타자 가상타자", "- 1구 헛스윙",
        "가상타자 : 삼진 아웃", "1루주자 가상주자 : 도루로 2루까지 진루",
    ] + three_outs()[:6]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    plays = [e for e in result.events if e["inning"] == 3 and e["half"] == "top"]
    assert [e["outcome"] for e in plays[:3]] == ["walk", "strikeout", "stolen_base"]
    assert plays[2]["outs_before"] == 1


def test_bases_loaded_hit_and_batter_advance_never_emit_four_runners():
    lines = [
        "4번타자 가상셋째", "가상셋째 : 우익수 오른쪽 3루타",
        "5번타자 가상둘째", "가상둘째 : 볼넷", "6번타자 가상첫째", "가상첫째 : 볼넷",
        "1루주자 가상둘째 : 2루까지 진루",
        "7번타자 가상타자", "가상타자 : 좌익수 왼쪽 1루타",
        "1루주자 가상타자 : 실책으로 2루까지 진루",
        "1루주자 가상첫째 : 3루까지 진루", "2루주자 가상둘째 : 홈인",
        "3루주자 가상셋째 : 홈인",
    ] + three_outs()
    result = normalize(source({(3, 0): lines}), "AA", "BB", 3, 0)
    assert result.complete
    assert all(0 <= e["runners_before"] <= 3 for e in result.events)
    error = next(e for e in result.events if e["outcome"] == "error")
    assert error["runners_before"] == 3


def test_mid_pa_review_requires_exact_pitch_name_and_corrected_type():
    review = "3회초 1번타순 2구 후 비디오 판독: 가상타자1 체크스윙 관련 노 스윙→스윙"
    lines = ["1번타자 가상타자1", "- 1구 볼", "- 2구 헛스윙", review,
             "- 3구 타격", "가상타자1 : 중견수 플라이 아웃"] + three_outs()[3:]
    assert normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete
    for incorrect in (review.replace("2구", "1구"), review.replace("가상타자1", "다른타자")):
        result = normalize(source({(3, 0): [incorrect if line == review else line for line in lines]}),
                           "AA", "BB", 1, 0)
        assert not result.complete and result.reason == "review_changed_or_unknown"


def test_finished_tie_needs_final_half_game_end_marker():
    result = normalize(source({(1, 0): three_outs(), (9, 1): three_outs() + ["경기종료"]}),
                       "AA", "BB", 0, 0)
    assert result.complete


def test_corrected_safe_steal_and_failed_double_steal_are_distinct():
    lines = ["4번타자 가상주자", "가상주자 : 볼넷", "5번타자 가상타자", "- 1구 볼",
             "1루주자 가상주자 : 도루로 2루까지 진루",
             "3회초 5번타순 1구 후 비디오 판독: 가상주자 2루 베이스차단 관련 아웃→세이프",
             "가상타자 : 볼넷", "6번타자 가상다음", "- 1구 볼",
             "1루주자 가상타자 : 이중도루 실패시 2루까지 진루",
             "2루주자 가상주자 : 도루실패아웃 (포수->3루수 태그아웃)",
             "가상다음 : 삼진 아웃"] + three_outs()[:3]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    assert len([e for e in result.events if e["outcome"] == "stolen_base"]) == 1
    assert len([e for e in result.events if e["outcome"] == "caught_stealing"]) == 1


def test_bunt_hit_and_foul_fly_error_preserve_distinct_events():
    lines = ["4번타자 가상타자", "- 1구 파울", "1구 포수 파울 플라이 포구 실책",
             "가상타자 : 3루수 앞 번트안타"] + three_outs()
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    plays = [e for e in result.events if e["inning"] == 3 and e["half"] == "top"]
    assert [e["outcome"] for e in plays[:2]] == ["error", "hit"]
    assert plays[0]["batter_name"] is None


def test_rain_pause_is_inert_and_batter_hit_by_batted_ball_is_explicit_out():
    lines = ["1번타자 가상타자1", "- 1구 볼",
             "3회초 1번타순 1구 후 20:10~20:20 (10분간) 우천 관련(으)로 경기 중단",
             "- 2구 타격", "가상타자1 : 타구맞음 아웃"] + three_outs()[3:]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert result.complete
    event = next(e for e in result.events if e['source_kind'] == 'batter_hit_by_batted_ball')
    assert event['outcome'] == 'out' and event['outs_before'] == 0


def test_missing_runner_departure_is_not_invented_to_resolve_base_collision():
    lines = ["4번타자 가상셋째", "가상셋째 : 우익수 오른쪽 3루타",
             "5번타자 가상둘째", "가상둘째 : 좌익수 왼쪽 2루타",
             "6번타자 가상타자", "가상타자 : 1루수 땅볼 아웃",
             "2루주자 가상둘째 : 3루까지 진루"] + three_outs()[:6]
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert not result.complete and result.reason == "runner_destination_collision"


def test_corrected_fair_ball_requires_matching_recorded_hit_and_pitch():
    review = "3회초 4번타순 2구 후 비디오 판독: 가상타자 외야타구 페어/파울 관련 파울→페어"
    lines = ["4번타자 가상타자", "- 1구 파울", "- 2구 타격", "가상타자 : 우익수 오른쪽 2루타",
             review] + three_outs()
    assert normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete
    lines[4] = review.replace("2구", "1구")
    result = normalize(source({(3, 0): lines}), "AA", "BB", 1, 0)
    assert not result.complete and result.reason == "review_changed_or_unknown"


def test_explicit_home_tag_review_matches_removed_third_base_runner():
    lines = ["4번타자 가상주자", "가상주자 : 우익수 오른쪽 3루타",
             "5번타자 가상타자", "- 1구 타격", "가상타자 : 좌익수 앞 1루타",
             "3루주자 가상주자 : 태그아웃 (좌익수->포수 태그아웃)",
             "3회초 5번타순 1구 후 비디오 판독: 가상주자 홈 태그 관련 세이프→아웃"] + three_outs()[:6]
    assert normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete
    lines[6] = lines[6].replace("가상주자 홈", "다른주자 홈")
    assert not normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete


def test_clever_runner_score_requires_pending_play_and_deflection_is_metadata():
    lines = ["4번타자 가상주자", "가상주자 : 우익수 오른쪽 3루타",
             "5번타자 가상타자", "- 1구 타격", "가상타자 : 좌중간 1루타",
             "3루주자 가상주자 : 주자의 재치로 홈인",
             "3회초 5번타순 1구 후 2루베이스 맞고 좌중간 방향으로 굴절"] + three_outs()
    assert normalize(source({(3, 0): lines}), "AA", "BB", 2, 0).complete
    standalone = lines[:2] + ["5번타자 가상타자", "- 1구 볼", lines[5]]
    assert not normalize(source({(3, 0): standalone}), "AA", "BB", 2, 0).complete


def test_standalone_check_swing_notice_requires_corrected_pitch_context():
    notice = "3회초 1번타순 1구 체크스윙 → 노 스윙 : 가상팀 가상타자1"
    lines = ["1번타자 가상타자1", "- 1구 볼", notice,
             "- 2구 타격", "가상타자1 : 중견수 플라이 아웃"] + three_outs()[3:]
    assert normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete
    for bad in (notice.replace("1구", "2구"), notice.replace("노 스윙", "스윙"),
                notice.replace("가상타자1", "다른타자"), notice.replace("3회초", "3회말")):
        result = normalize(source({(3, 0): [bad if line == notice else line for line in lines]}),
                           "AA", "BB", 1, 0)
        assert not result.complete and result.reason == "review_changed_or_unknown"


def test_three_foot_notice_requires_same_batter_pitch_and_explicit_out():
    notice = "3회초 1번타순 1구 후 3피트 라인 아웃: 가상팀 가상타자1"
    lines = three_outs()[:3] + [notice] + three_outs()[3:]
    assert normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete
    for bad in (notice.replace("1구", "2구"), notice.replace("가상타자1", "다른타자")):
        assert not normalize(source({(3, 0): [bad if line == notice else line for line in lines]}),
                             "AA", "BB", 1, 0).complete


def test_first_base_batted_safe_review_matches_actual_batter_destination():
    lines = ["4번타자 가상타자", "- 1구 타격", "가상타자 : 1루수 왼쪽 내야안타",
             "3회초 4번타순 1구 후 비디오 판독: 가상타자 1루 타구 관련 아웃→세이프"] + three_outs()
    assert normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete
    lines[2] = "가상타자 : 우익수 오른쪽 2루타"
    assert not normalize(source({(3, 0): lines}), "AA", "BB", 1, 0).complete
