import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { createGamesApi, type GameSnapshot } from '../../api/games';
import { Button, Card, s } from '../../ui';
import { useTeamVisual } from '../../team-visual';

const api = createGamesApi(process.env.EXPO_PUBLIC_API_URL);

export default function ServerGame() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <Details key={id} id={id} />;
}

function Details({ id }: { id: string }) {
  const visual = useTeamVisual();
  const [game, setGame] = useState<GameSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void api.detail(id, controller.signal).then(value => { if (!controller.signal.aborted) setGame(value); }).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof Error ? error.message : '기록을 불러오지 못했어요.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, attempt]);
  const reload = () => { setLoading(true); setError(''); setGame(null); setAttempt(value => value + 1); };
  return <ScrollView style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content}>
    {loading ? <ActivityIndicator accessibilityLabel="경기 상세 불러오는 중" color={visual.accent} /> : error ? <Card>
      <Text accessibilityRole="alert" style={s.body}>{error}</Text>
      <Button title="다시 시도" onPress={reload} />
    </Card> : game ? <>
      <Text style={s.eyebrow}>과거 조회 자료 · 실시간 아님</Text>
      <Text style={s.title}>{game.away_team_id} vs {game.home_team_id}</Text>
      <Card>
        <Text style={s.heading}>{game.away_runs} : {game.home_runs}</Text>
        <Text style={s.body}>경기 날짜 · {game.game_date}</Text>
        <Text style={s.body}>서버 수집 시각 · {new Date(game.collected_at).toLocaleString()}</Text>
        <Text style={s.body}>출처 · KBO 공개 페이지 조회 자료</Text>
      </Card>
      <Text style={s.body}>이 점수는 서버에 저장된 조회 시점의 값이에요. 선수별 사건과 경기 상황의 검증이 아직 끝나지 않아 멘탈 지수를 계산하지 않아요.</Text>
      <Text style={s.body}>수집 시각은 서버가 자료를 확인한 시각이며, 실제 경기 사건 발생 시각이 아니에요.</Text>
      <Button title="새로고침" onPress={reload} />
    </> : null}
  </ScrollView>;
}
