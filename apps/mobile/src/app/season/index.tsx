import { useCallback, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, ScrollView, Text, View } from 'react-native';
import { router } from 'expo-router';
import { createGamesApi, type SeasonGame } from '../../api/games';
import { YearMonthPicker } from '../../YearMonthPicker';
import { teams, teamName, indexLabel } from '../../domain/teams';
import { useRemote } from '../../hooks/useRemote';
import { Button, Card, colors, s } from '../../ui';

const api = createGamesApi(process.env.EXPO_PUBLIC_API_URL);
const statusLabel = { completed: '경기 종료', scheduled: '예정', cancelled: '취소', unknown: '상태 확인 중' } as const;

export default function Season() {
  const [team, setTeam] = useState('');
  const [season, setSeason] = useState(2026);
  const [month, setMonth] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = `${season}:${team}:${month}:${attempt}`;
  const load = useCallback((signal: AbortSignal) => api.season(season, { team, month: month ?? undefined }, signal), [season, team, month]);
  const { loading, data, error } = useRemote(key, load);
  const openGame = (game: SeasonGame, perspective: string) => router.push({ pathname: '/season/[id]', params: { id: game.game_id, team: perspective } });
  return <FlatList style={s.page} contentContainerStyle={s.content} data={data?.games ?? []} keyExtractor={game => game.game_id} initialNumToRender={12}
    ListHeaderComponent={<View style={{ gap: 18 }}>
      <Text style={s.eyebrow}>지난 경기, 다시 보는 마음</Text>
      <Text style={s.title}>{season} 시즌 멘탈지수</Text>
      <Text style={s.body}>정규시즌·포스트시즌 · 시범경기 제외</Text>
      <Text style={s.body}>경기 기록을 바탕으로 계산한 재미용 지수예요. 직접 관람하지 않은 경기도 팀 관점으로 볼 수 있어요. 내 감정이나 관람 기록을 측정한 값은 아니에요.</Text>
      <Text style={s.heading}>응원팀으로 찾기</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        {[{ id: '', name: '전체' }, ...teams].map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`${item.name} 경기 필터`} accessibilityState={{ selected: team === item.id }}
          onPress={() => setTeam(item.id)} style={{ paddingHorizontal: 18, paddingVertical: 14, minHeight: 50, borderRadius: 999, borderWidth: 1, borderColor: colors.line, backgroundColor: team === item.id ? colors.primary : colors.bg }}>
          <Text style={{ color: team === item.id ? colors.onPrimary : colors.ink, fontWeight: '700' }}>{team === item.id ? '✓ ' : ''}{item.name}</Text>
        </Pressable>)}
      </ScrollView>
      <YearMonthPicker year={season} month={month} allowAll onChange={(year, value) => { setSeason(year); setMonth(value); }} />
      <Text style={s.body}>{team ? teamName(team) : '전체 팀'} · {season}년 {month === null ? '전체 월' : `${month}월`}</Text>
      {data ? <Card>
        <Text style={s.heading}>조회된 종료 경기 {data.coverage.completed}경기</Text>
        <Text style={s.body}>지수 확인 가능 {data.coverage.indexed} · 자료 확인 중 {data.coverage.incomplete} · 준비 전 {data.coverage.missing}</Text>
        <Text style={s.body}>준비되지 않은 지수는 0점이 아니에요. 데이터가 확보되면 추가돼요.</Text>
      </Card> : null}
      {loading ? <><ActivityIndicator color={colors.green} accessibilityLabel="시즌 경기 불러오는 중" /><Text style={s.body}>시즌 경기를 불러오는 중이에요.</Text></> : error ? <Card>
        <Text accessibilityRole="alert" style={s.body}>{error}</Text><Button title="다시 시도" onPress={() => setAttempt(value => value + 1)} />
      </Card> : null}
    </View>}
    ListEmptyComponent={!loading && !error ? <Text style={s.body}>조회 조건에 맞는 경기가 아직 등록되지 않았어요. 실제 경기 유무를 뜻하지는 않아요.</Text> : undefined}
    renderItem={({ item }) => <Card>
      <Text style={s.eyebrow}>{item.game_date} · {statusLabel[item.status]}</Text>
      <Text style={s.heading}>{teamName(item.away_team_id)} {item.away_runs ?? '—'} : {item.home_runs ?? '—'} {teamName(item.home_team_id)}</Text>
      {item.venue ? <Text style={s.body}>{item.venue}</Text> : null}
      <Text style={s.body}>{indexLabel[item.index_status]}</Text>
      {item.status === 'completed' ? <>
        <Text style={s.body}>어느 팀의 마음으로 볼까요?</Text>
        <View style={{ gap: 10 }}>
          <Button title={`${teamName(item.away_team_id)} 관점으로 보기`} onPress={() => openGame(item, item.away_team_id)} />
          <Button title={`${teamName(item.home_team_id)} 관점으로 보기`} onPress={() => openGame(item, item.home_team_id)} />
        </View>
      </> : <Text style={s.body}>종료된 경기의 자료가 준비되면 지수를 볼 수 있어요.</Text>}
    </Card>} />;
}
