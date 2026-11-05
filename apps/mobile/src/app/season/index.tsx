import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { Stack, router } from 'expo-router';
import { createGamesApi, type SeasonGame } from '../../api/games';
import { YearMonthPicker } from '../../YearMonthPicker';
import { teams, teamName, indexLabel } from '../../domain/teams';
import { latestCompletedMonth, seasonMonths } from '../../domain/season-month';
import { useRemote } from '../../hooks/useRemote';
import { useTeamPreference } from '../../team-preference';
import { teamVisuals, useTeamVisual } from '../../team-visual';
import { Button, Card, colors, s } from '../../ui';

const api = createGamesApi(process.env.EXPO_PUBLIC_API_URL);
const season = 2026;
const statusLabel = { completed: '경기 종료', scheduled: '예정', cancelled: '취소', unknown: '상태 확인 중' } as const;
type Picker = 'team' | 'month' | null;

export default function Season() {
  const { teamId } = useTeamPreference();
  return <SeasonContent key={teamId} preferredTeam={teamId ?? ''} />;
}

function SeasonContent({ preferredTeam }: { preferredTeam: string }) {
  const [team, setTeam] = useState(preferredTeam);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [picker, setPicker] = useState<Picker>(null);
  const [attempt, setAttempt] = useState(0);
  const visual = useTeamVisual(team);
  const load = useCallback((signal: AbortSignal) => api.season(season, { team }, signal), [team]);
  const { loading, data, error } = useRemote(`${season}:${team}:${attempt}`, load);
  const availableMonths = useMemo(() => seasonMonths(data?.games ?? []), [data]);
  const month = selectedMonth ?? latestCompletedMonth(data?.games ?? []) ?? availableMonths[0];
  const games = useMemo(() => (data?.games ?? []).filter(game => Number(game.game_date.slice(5, 7)) === month), [data, month]);
  const completed = games.filter(game => game.status === 'completed');
  const indexed = completed.filter(game => game.index_status === 'ready').length;
  const incomplete = completed.filter(game => game.index_status === 'incomplete').length;
  const missing = completed.filter(game => game.index_status === 'missing').length;
  const openGame = (game: SeasonGame) => router.push({ pathname: '/season/[id]', params: { id: game.game_id, team } });

  return <>
    <Stack.Screen options={{ title: '왜저럴까', headerRight: () => <Pressable accessibilityRole="button" accessibilityLabel="설정 열기" onPress={() => router.push('/settings')} style={{ paddingHorizontal: 8, paddingVertical: 10 }}><Text style={{ color: visual.accent, fontSize: 22 }}>☰</Text></Pressable> }} />
    <FlatList style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content} data={games} keyExtractor={game => game.game_id} initialNumToRender={12}
      ListHeaderComponent={<View style={{ gap: 17 }}>
        <View style={{ alignItems: 'center', paddingTop: 12, gap: 8 }}>
          <View style={{ width: 116, height: 116, borderRadius: 34, alignItems: 'center', justifyContent: 'center', backgroundColor: visual.soft }}>
            <Text accessibilityLabel={`${teamName(team)} 상징 이모지`} style={{ fontSize: team === 'LG' ? 40 : 65 }}>{visual.emoji}</Text>
          </View>
          <Text style={[s.eyebrow, { color: visual.accent }]}>{teamName(team)} 팬의 관전석</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="연도와 월 선택" onPress={() => setPicker('month')} style={{ minHeight: 52, justifyContent: 'center', alignItems: 'center' }}>
            <Text style={s.title}>{season}년 {month}월 ⌄</Text>
          </Pressable>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel={`${teamName(team)} 경기 필터`} onPress={() => setPicker('team')}
          style={{ borderRadius: 20, backgroundColor: visual.soft, padding: 16, minHeight: 54 }}>
          <Text style={[s.heading, { color: visual.accent, fontSize: 17 }]}>{teamVisuals[team]?.emoji ?? '⚾'}  {teamName(team)} 경기만 보기  ⌄</Text>
        </Pressable>
        <Text style={s.body}>정규시즌·포스트시즌 · 시범경기 제외</Text>
        {data ? <Card>
          <Text style={s.heading}>이달 종료 경기 {completed.length}경기</Text>
          <Text style={s.body}>지수 확인 가능 {indexed} · 자료 확인 중 {incomplete} · 준비 전 {missing}</Text>
          <Text style={s.body}>경기 기록으로 계산한 재미용 지수예요. 직접 관람하지 않은 경기도 볼 수 있어요.</Text>
        </Card> : null}
        {loading ? <><ActivityIndicator color={visual.accent} accessibilityLabel="시즌 경기 불러오는 중" /><Text style={s.body}>시즌 경기를 불러오는 중이에요.</Text></> : error ? <Card>
          <Text accessibilityRole="alert" style={s.body}>{error}</Text><Button title="다시 시도" onPress={() => setAttempt(value => value + 1)} />
        </Card> : null}
      </View>}
      ListEmptyComponent={!loading && !error ? <Text style={s.body}>이달의 경기 기록이 아직 등록되지 않았어요. 실제 경기 유무를 뜻하지는 않아요.</Text> : undefined}
      renderItem={({ item }) => <Card>
        <Text style={[s.eyebrow, { color: visual.accent }]}>{item.game_date} · {statusLabel[item.status]}</Text>
        <Text style={s.heading}>{teamName(item.away_team_id)} {item.away_runs ?? '—'} : {item.home_runs ?? '—'} {teamName(item.home_team_id)}</Text>
        {item.venue ? <Text style={s.body}>{item.venue}</Text> : null}
        <Text style={s.body}>{indexLabel[item.index_status]}</Text>
        {item.status === 'completed' ? <Button title={`${teamName(team)} 관점 멘탈지수 보기`} onPress={() => openGame(item)} /> : <Text style={s.body}>경기가 끝나고 자료가 준비되면 지수를 볼 수 있어요.</Text>}
      </Card>} />
    <Modal visible={picker !== null} transparent animationType="slide" onRequestClose={() => setPicker(null)}>
      <View style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: '#0009' }}>
        <View style={{ backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, maxHeight: '75%', padding: 24, gap: 16 }}>
          <View style={s.row}><Text style={s.heading}>{picker === 'team' ? '어느 팀 경기를 볼까요?' : '연도와 월 선택'}</Text><Pressable accessibilityRole="button" accessibilityLabel="선택 닫기" onPress={() => setPicker(null)}><Text style={s.body}>닫기 ✕</Text></Pressable></View>
          <ScrollView contentContainerStyle={{ gap: 10 }}>
            {picker === 'team' ? teams.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`${item.name} 경기 필터`} accessibilityState={{ selected: team === item.id }}
              onPress={() => { setTeam(item.id); setSelectedMonth(null); setPicker(null); }} style={{ minHeight: 54, borderRadius: 18, padding: 14, backgroundColor: team === item.id ? teamVisuals[item.id].soft : colors.bg }}>
              <Text style={[s.heading, { fontSize: 17, color: team === item.id ? teamVisuals[item.id].accent : colors.ink }]}>{teamVisuals[item.id].emoji}  {item.name}{team === item.id ? '  ✓' : ''}</Text>
            </Pressable>) : <YearMonthPicker year={season} month={month} availableMonths={availableMonths} onChange={(_, value) => { setSelectedMonth(value); setPicker(null); }} />}
          </ScrollView>
        </View>
      </View>
    </Modal>
  </>;
}
