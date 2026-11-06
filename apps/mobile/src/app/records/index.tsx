import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text } from 'react-native';
import { router } from 'expo-router';
import { createGamesApi, type GameSnapshot } from '../../api/games';
import { YearMonthPicker } from '../../YearMonthPicker';
import { Button, Card, s } from '../../ui';
import { appearance as visual } from '../../theme';

const api = createGamesApi(process.env.EXPO_PUBLIC_API_URL);
const currentMonthInKorea = () => new Date(Date.now() + 9 * 60 * 60 * 1000).getUTCMonth() + 1;

export default function Records() {
  const [year, setYear] = useState(2026);
  const [month, setMonth] = useState(currentMonthInKorea);
  const [attempt, setAttempt] = useState(0);
  const [games, setGames] = useState<GameSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    void api.listMonth(year, month, controller.signal).then(value => { if (!controller.signal.aborted) setGames(value); }).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof Error ? error.message : '기록을 불러오지 못했어요.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [year, month, attempt]);
  const reload = () => { setLoading(true); setError(''); setGames([]); setAttempt(value => value + 1); };
  return <ScrollView style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content}>
    <Text style={s.title}>서버 경기 기록</Text>
    <Text style={s.body}>서버에 저장된 과거 경기 조회 결과예요. 실시간 중계·개인 멘탈 기록과는 별개이며, 아직 검증 중인 자료예요.</Text>
    <YearMonthPicker year={year} month={month} onChange={(value, selected) => { setYear(value); if (selected !== null) setMonth(selected); reload(); }} />
    <Text style={s.eyebrow}>조회 기준 · {year}년 {month}월</Text>
    {loading ? <><ActivityIndicator accessibilityLabel="경기 기록 불러오는 중" color={visual.accent} /><Text style={s.body}>기록을 불러오는 중이에요.</Text></> : error ? <Card>
      <Text accessibilityRole="alert" style={s.body}>{error}</Text>
      <Button title="다시 시도" onPress={reload} />
    </Card> : games.length === 0 ? <Text style={s.body}>이 달에 저장된 경기 기록이 없어요. 실제 경기 일정이 없다는 뜻은 아니에요.</Text> : games.map(game => <Card key={game.game_id}>
      <Text style={s.eyebrow}>{game.game_date} · 과거 조회 자료</Text>
      <Text style={s.heading}>{game.away_team_id} {game.away_runs} : {game.home_runs} {game.home_team_id}</Text>
      <Text style={s.body}>서버 수집 시각 · {new Date(game.collected_at).toLocaleString()}</Text>
      <Button title="서버 기록 보기" onPress={() => router.push({ pathname: '/records/[id]', params: { id: game.game_id } })} />
    </Card>)}
  </ScrollView>;
}
