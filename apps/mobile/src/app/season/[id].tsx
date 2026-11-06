import { LoadingSkeleton, SkeletonBlock } from '../../LoadingSkeleton';
import { groupStressEvents, stressChange } from '../../domain/stress-timeline';
import { useCallback, useMemo, useState } from 'react';
import { SectionList, Text, View } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { createGamesApi } from '../../api/games';
import { teamName, indexLabel, mentalReason, gameIdentity } from '../../domain/teams';
import { useRemote } from '../../hooks/useRemote';
import { Button, Card, colors, s } from '../../ui';
import { useTeamVisual } from '../../team-visual';

const api = createGamesApi(process.env.EXPO_PUBLIC_API_URL, fetch, 45_000);
const outcomes: Record<string, string> = {
  strikeout: '삼진', groundout: '땅볼 아웃', flyout: '뜬공 아웃', double_play: '병살타', triple_play: '삼중살', strikeout_reached: '낫아웃 출루', runner_advance: '주자 진루', error: '실책',
  single: '안타', double: '2루타', triple: '3루타', home_run: '홈런', walk: '볼넷', hit_by_pitch: '몸에 맞는 공',
  out: '아웃', hit: '안타', sacrifice: '희생타', score: '득점',
  wild_pitch: '폭투', passed_ball: '포일', balk: '보크', stolen_base: '도루',
  caught_stealing: '도루 실패', fielders_choice: '야수선택',
};

export default function SeasonGame() {
  const params = useLocalSearchParams<{ id: string; team?: string }>();
  const id = typeof params.id === 'string' ? params.id : '';
  const team = typeof params.team === 'string' ? params.team : '';
  return <Detail key={`${id}:${team}`} id={id} team={team} />;
}

function Detail({ id, team }: { id: string; team: string }) {
  const visual = useTeamVisual();
  const [attempt, setAttempt] = useState(0);
  const key = `${id}:${team}:${attempt}`;
  const load = useCallback((signal: AbortSignal) => api.mental(id, team, signal), [id, team]);
  const { loading, data, error } = useRemote(key, load);
  const identity = gameIdentity(id);
  const loadScore = useCallback(async (signal: AbortSignal) => {
    const game = gameIdentity(id);
    if (!game) throw new Error('경기 정보를 확인할 수 없어요.');
    const season = await api.season(Number(game.date.slice(0, 4)), { month: Number(game.date.slice(5, 7)), team }, signal);
    return season.games.find(item => item.game_id === id) ?? null;
  }, [id, team]);
  const scoreboard = useRemote(key, loadScore);
  const sections = useMemo(() => groupStressEvents(data?.status === 'ready' ? data.events : []), [data]);
  const other = identity && (team === identity.away ? identity.home : team === identity.home ? identity.away : null);
  const ready = data?.status === 'ready';
  return <SectionList stickySectionHeadersEnabled={false} style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={[s.content, { gap: 0 }]} sections={sections} keyExtractor={event => event.event_id} initialNumToRender={15}
    ListHeaderComponent={<View style={{ gap: 18 }}>
      <Text style={s.eyebrow}>{teamName(team)} 관점 · 지난 경기</Text>
      <Text style={s.title}>그날의 스트레스</Text>
      <View style={{ padding: 22, borderRadius: 24, backgroundColor: visual.surface, gap: 14 }}>
        <Text style={[s.eyebrow, { color: visual.accent }]}>최종 스코어</Text>
        {scoreboard.loading ? <View accessible accessibilityLabel="최종 점수 불러오는 중"><SkeletonBlock height={64} /></View> : scoreboard.data?.status === 'completed' && scoreboard.data.away_runs !== null && scoreboard.data.home_runs !== null ?
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <View style={{ flex: 1, alignItems: 'center', gap: 8 }}><Text style={s.heading}>{teamName(scoreboard.data.away_team_id)}</Text><Text style={{ fontFamily: 'BagelFatOne', fontSize: 48, color: colors.ink }}>{scoreboard.data.away_runs}</Text><Text style={s.body}>원정</Text></View>
            <Text style={s.heading}>:</Text>
            <View style={{ flex: 1, alignItems: 'center', gap: 8 }}><Text style={s.heading}>{teamName(scoreboard.data.home_team_id)}</Text><Text style={{ fontFamily: 'BagelFatOne', fontSize: 48, color: colors.ink }}>{scoreboard.data.home_runs}</Text><Text style={s.body}>홈</Text></View>
          </View> : <><Text style={s.body}>{scoreboard.error ?? '최종 점수를 아직 확인할 수 없어요.'}</Text><Button title="점수 다시 불러오기" onPress={() => setAttempt(value => value + 1)} /></>}
      </View>
      {identity ? <Text style={s.heading}>{identity.date} · {teamName(identity.away)} vs {teamName(identity.home)}</Text> : null}
      <Text style={s.body}>경기 기록과 계산 모델로 만든 재미용 지수예요. 의학적 지표나 개인의 실제 감정·관람 기록이 아니에요.</Text>
      {other && /^[A-Z]{2}$/.test(other) ? <Button title={`${teamName(other)} 관점으로 바꾸기`} onPress={() => router.replace({ pathname: '/season/[id]', params: { id, team: other } })} /> : null}
      {loading ? <LoadingSkeleton label="스트레스 지수 불러오는 중" /> : error ? <Card>
        <Text accessibilityRole="alert" style={s.body}>{error}</Text><Button title="다시 시도" onPress={() => setAttempt(value => value + 1)} />
      </Card> : data ? <>
        {ready ? <Card>
          <Text style={s.heading}>경기 종료 스트레스</Text>
          <Text accessibilityLabel={`종료 스트레스 지수 ${data.score}점`} style={{ fontFamily: 'BagelFatOne', fontSize: 64, color: colors.ink }}>{data.score}<Text style={{ fontSize: 20 }}> / 100</Text></Text>
          <Text style={s.body}>최고 지수 {data.peak_score}점 · 누적 변화 {data.raw_total !== null && data.raw_total > 0 ? '+' : ''}{data.raw_total}점</Text>
          <Text style={s.body}>스트레스가 쌓이면 +, 해소되면 −예요. 지수는 0~100 범위예요.</Text>
        </Card> : <Card>
          <Text style={s.heading}>{indexLabel[data.status]}</Text>
          <Text style={s.body}>{mentalReason(data.reason, data.status)}</Text>
          <Text style={s.body}>0점이나 평온한 경기라는 뜻은 아니에요.</Text>
        </Card>}
        {ready ? <Text style={s.heading}>경기 흐름</Text> : null}
      </> : null}
    </View>}
    ListFooterComponent={!loading ? <View style={{ paddingTop: 24 }}><Button title="새로고침" onPress={() => setAttempt(value => value + 1)} /></View> : undefined}
    ListEmptyComponent={ready ? <Text style={s.body}>표시할 사건이 없어요.</Text> : undefined}
    renderSectionHeader={({ section }) => <View style={{ gap: 12, paddingTop: section.firstInningSection ? 24 : 16, paddingBottom: 12 }}>
      {section.firstInningSection ? <Text accessibilityRole="header" style={[s.title, { fontSize: 28 }]}>{section.inning}회</Text> : null}
      <Text accessibilityRole="header" style={[s.heading, { color: visual.accent }]}>{section.half === 'top' ? '초' : '말'} · {identity ? teamName(section.half === 'top' ? identity.away : identity.home) : ''} 공격</Text>
    </View>}
    renderItem={({ item }) => <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, paddingVertical: 18, borderBottomWidth: 1, borderColor: visual.border }}>
      <View style={{ flex: 1, minWidth: 0, gap: 6 }}>
        <Text style={s.heading}>{item.batter_name ?? '선수 정보 없음'}</Text>
        <Text style={[s.body, { color: colors.ink }]}>{outcomes[item.outcome] ?? item.outcome}</Text>
      </View>
      <View style={{ flexShrink: 0, alignItems: 'flex-end', gap: 6 }}>
        <Text accessibilityLabel={`스트레스 ${item.delta > 0 ? '증가' : item.delta < 0 ? '해소' : '변화 없음'} ${Math.abs(item.delta)}점`} style={{ color: item.delta > 0 ? colors.orange : item.delta < 0 ? colors.green : colors.muted, fontSize: 24, fontWeight: '700', fontVariant: ['tabular-nums'] }}>{stressChange(item.delta)}</Text>
        <Text style={[s.body, { fontSize: 12 }]}>현재 {item.score_after} / 100</Text>
      </View>
    </View>} />;
}
