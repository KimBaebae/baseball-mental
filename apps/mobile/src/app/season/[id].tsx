import { useCallback, useState } from 'react';
import { ActivityIndicator, FlatList, Text, View } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { createGamesApi } from '../../api/games';
import { teamName, indexLabel, mentalReason, gameIdentity } from '../../domain/teams';
import { useRemote } from '../../hooks/useRemote';
import { Button, Card, colors, s } from '../../ui';
import { useTeamVisual } from '../../team-visual';

const api = createGamesApi(process.env.EXPO_PUBLIC_API_URL);
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
  const other = identity && (team === identity.away ? identity.home : team === identity.home ? identity.away : null);
  const ready = data?.status === 'ready';
  return <FlatList style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content} data={ready ? data.events : []} keyExtractor={event => event.event_id} initialNumToRender={15}
    ListHeaderComponent={<View style={{ gap: 18 }}>
      <Text style={s.eyebrow}>{teamName(team)} 관점 · 지난 경기</Text>
      <Text style={s.title}>그날의 멘탈지수</Text>
      {identity ? <Text style={s.heading}>{identity.date} · {teamName(identity.away)} vs {teamName(identity.home)}</Text> : null}
      <Text style={s.body}>경기 기록과 계산 모델로 만든 재미용 지수예요. 의학적 지표나 개인의 실제 감정·관람 기록이 아니에요.</Text>
      {other && /^[A-Z]{2}$/.test(other) ? <Button title={`${teamName(other)} 관점으로 바꾸기`} onPress={() => router.replace({ pathname: '/season/[id]', params: { id, team: other } })} /> : null}
      {loading ? <><ActivityIndicator color={visual.accent} accessibilityLabel="멘탈지수 불러오는 중" /><Text style={s.body}>경기 흐름을 불러오는 중이에요.</Text></> : error ? <Card>
        <Text accessibilityRole="alert" style={s.body}>{error}</Text><Button title="다시 시도" onPress={() => setAttempt(value => value + 1)} />
      </Card> : data ? <>
        {ready ? <Card>
          <Text style={s.heading}>경기 종료 시점</Text>
          <Text accessibilityLabel={`종료 멘탈지수 ${data.score}점`} style={{ fontFamily: 'BagelFatOne', fontSize: 64, color: colors.ink }}>{data.score}<Text style={{ fontSize: 20 }}> / 100</Text></Text>
          <Text style={s.body}>최고 지수 {data.peak_score}점 · 누적 변화 {data.raw_total !== null && data.raw_total > 0 ? '+' : ''}{data.raw_total}점</Text>
          <Text style={s.body}>지수는 0~100 범위예요. 양수는 스트레스 증가, 음수는 회복을 뜻해요.</Text>
        </Card> : <Card>
          <Text style={s.heading}>{indexLabel[data.status]}</Text>
          <Text style={s.body}>{mentalReason(data.reason, data.status)}</Text>
          <Text style={s.body}>0점이나 평온한 경기라는 뜻은 아니에요.</Text>
        </Card>}
        {data.computed_at ? <Text style={s.body}>계산 시각 · {new Date(data.computed_at).toLocaleString()}</Text> : null}
        <Text style={s.body}>계산 모델 · {data.model_version}</Text>
        <Button title="새로고침" onPress={() => setAttempt(value => value + 1)} />
        {ready ? <Text style={s.heading}>경기 흐름</Text> : null}
      </> : null}
    </View>}
    ListEmptyComponent={ready ? <Text style={s.body}>표시할 사건이 없어요.</Text> : undefined}
    renderItem={({ item }) => <Card>
      <Text style={s.eyebrow}>{item.inning}회 {item.half === 'top' ? '초' : '말'}{item.batter_name ? ` · ${item.batter_name}` : ''}</Text>
      <Text style={s.heading}>{outcomes[item.outcome] ?? item.outcome}</Text>
      <Text style={{ color: item.delta > 0 ? colors.orange : item.delta < 0 ? colors.green : colors.muted, fontSize: 24, fontWeight: '700' }}>{item.delta > 0 ? '+' : ''}{item.delta}점 · 지수 {item.score_after}</Text>
    </Card>} />;
}
