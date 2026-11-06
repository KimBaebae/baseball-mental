import { LoadingSkeleton, SkeletonBlock } from '../../LoadingSkeleton';
import { TeamCharacter } from '../../TeamCharacter';
import { StadiumHero } from '../../StadiumHero';
import { useCallback, useMemo, useState } from 'react';
import { FlatList, Modal, Pressable, ScrollView, Text, View, useWindowDimensions } from 'react-native';
import { Stack, router } from 'expo-router';
import { createGamesApi, type SeasonGame } from '../../api/games';
import { YearMonthPicker } from '../../YearMonthPicker';
import { teams, teamName, indexLabel } from '../../domain/teams';
import { latestCompletedMonth, seasonMonths } from '../../domain/season-month';
import { useRemote } from '../../hooks/useRemote';
import { useTeamPreference } from '../../team-preference';
import { appearance as visual } from '../../theme';
import { Button, Card, colors, s } from '../../ui';

// Render Free may need time to wake before the first season request.
const api = createGamesApi(process.env.EXPO_PUBLIC_API_URL, fetch, 45_000);
const season = 2026;
const statusLabel = { completed: '경기 종료', scheduled: '예정', cancelled: '취소', unknown: '상태 확인 중' } as const;
type Picker = 'team' | 'month' | null;

export default function Season() {
  const { teamId } = useTeamPreference();
  return <SeasonContent key={teamId} preferredTeam={teamId ?? ''} />;
}

function SeasonContent({ preferredTeam }: { preferredTeam: string }) {
  const { width } = useWindowDimensions();
  const [team, setTeam] = useState(preferredTeam);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [picker, setPicker] = useState<Picker>(null);
  const [attempt, setAttempt] = useState(0);
  const load = useCallback((signal: AbortSignal) => api.season(season, {}, signal), []);
  const { loading, data, error } = useRemote(`${season}:${attempt}`, load);
  const availableMonths = useMemo(() => seasonMonths(data?.games ?? []), [data]);
  const teamGames = useMemo(() => (data?.games ?? []).filter(game => game.away_team_id === team || game.home_team_id === team), [data, team]);
  const month = selectedMonth ?? latestCompletedMonth(teamGames) ?? availableMonths[0];
  const games = useMemo(() => teamGames.filter(game => Number(game.game_date.slice(5, 7)) === month), [teamGames, month]);
  const completed = games.filter(game => game.status === 'completed');
  const indexed = completed.filter(game => game.index_status === 'ready').length;
  const incomplete = completed.filter(game => game.index_status === 'incomplete').length;
  const missing = completed.filter(game => game.index_status === 'missing').length;
  const openGame = (game: SeasonGame) => router.push({ pathname: '/season/[id]', params: { id: game.game_id, team } });

  return <>
    <Stack.Screen options={{ title: '왜저럴까', headerRight: () => <Pressable accessibilityRole="button" accessibilityLabel="설정 열기" onPress={() => router.push('/settings')} style={{ paddingHorizontal: 8, paddingVertical: 10 }}><Text style={{ color: visual.accent, fontSize: 22 }}>☰</Text></Pressable> }} />
    <FlatList style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={[s.content, { paddingTop: 0, gap: 0 }]} data={games} keyExtractor={game => game.game_id} initialNumToRender={12}
      ListHeaderComponent={<View style={{ gap: 17 }}>
        <StadiumHero>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <TeamCharacter teamId={preferredTeam} size={36} />
            <Text style={[s.eyebrow, { color: colors.ink, letterSpacing: 0.5 }]}>{teamName(preferredTeam)} 팬의 관전석</Text>
          </View>
          <Text style={[s.title, { fontSize: width < 360 ? 30 : 36 }]}>{'오늘도, 끝까지 응원해.'}</Text>
        </StadiumHero>
        <View style={[s.row, { borderTopWidth: 1, borderColor: colors.line, paddingTop: 12, flexWrap: 'wrap' }]}>
          {loading ? <View accessible accessibilityLabel="최근 경기 월 확인 중" style={{ paddingVertical: 12 }}><SkeletonBlock width={160} height={28} /></View> : <Pressable accessibilityRole="button" accessibilityLabel="연도와 월 선택" onPress={() => setPicker('month')} style={{ minHeight: 48, justifyContent: 'center' }}>
            <Text style={s.heading}>{season}년{month ? ` ${month}월` : ''} ⌄</Text>
          </Pressable>}
          <Pressable accessibilityRole="button" accessibilityLabel={`${teamName(team)} 경기 필터`} onPress={() => setPicker('team')}
            style={{ borderRadius: 999, borderWidth: 1, borderColor: visual.border, paddingHorizontal: 16, paddingVertical: 12, minHeight: 48, justifyContent: 'center' }}>
            <Text style={[s.body, { color: colors.ink }]}>{teamName(team)} 경기  ⌄</Text>
          </Pressable>
        </View>
        {data ? <Text style={s.body}>종료 {completed.length}경기 · 지수 확인 가능 {indexed}{incomplete || missing ? ` · 준비 중 ${incomplete + missing}` : ''}</Text> : null}
        {loading ? <LoadingSkeleton label="시즌 경기 불러오는 중" /> : error ? <Card>
          <Text accessibilityRole="alert" style={s.body}>{error}</Text><Button title="다시 시도" onPress={() => setAttempt(value => value + 1)} />
        </Card> : null}
      </View>}
      ListEmptyComponent={!loading && !error ? <Text style={s.body}>이달의 경기 기록이 아직 등록되지 않았어요. 실제 경기 유무를 뜻하지는 않아요.</Text> : undefined}
      renderItem={({ item }) => <Card>
        <Text style={[s.eyebrow, { letterSpacing: 0.5 }]}>{item.game_date} · {item.venue ? `${item.venue} · ` : ''}{statusLabel[item.status]}</Text>
        <View style={[s.row, { paddingVertical: 4 }]}>
          <Text style={[s.heading, { flex: 1, textAlign: 'center' }]}>{teamName(item.away_team_id)}</Text>
          <Text accessibilityLabel={`원정 ${item.away_runs ?? '미확인'} 대 홈 ${item.home_runs ?? '미확인'}`} style={[s.title, { fontSize: 40, flexShrink: 1 }]}>{item.away_runs ?? '—'} : {item.home_runs ?? '—'}</Text>
          <Text style={[s.heading, { flex: 1, textAlign: 'center' }]}>{teamName(item.home_team_id)}</Text>
        </View>
        {item.index_status !== 'ready' ? <Text style={s.body}>{indexLabel[item.index_status]}</Text> : null}
        {item.status === 'completed' ? <Button title={`${teamName(team)} 관점 스트레스 지수 보기`} onPress={() => openGame(item)} /> : <Text style={s.body}>경기가 끝나고 자료가 준비되면 지수를 볼 수 있어요.</Text>}
      </Card>}
      ListFooterComponent={<View style={{ paddingTop: 24, gap: 8 }}><Text style={s.body}>정규시즌·포스트시즌 · 시범경기 제외</Text><Text style={s.body}>경기 기록으로 계산한 재미용 지수예요. 직접 관람하지 않은 경기도 볼 수 있어요.</Text></View>} />
    <Modal visible={picker !== null} transparent animationType="slide" onRequestClose={() => setPicker(null)}>
      <View style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: '#0009' }}>
        <View style={{ backgroundColor: visual.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, maxHeight: '75%', padding: 24, gap: 16 }}>
          <View style={s.row}><Text style={s.heading}>{picker === 'team' ? '어느 팀 경기를 볼까요?' : '연도와 월 선택'}</Text><Pressable accessibilityRole="button" accessibilityLabel="선택 닫기" onPress={() => setPicker(null)}><Text style={s.body}>닫기 ✕</Text></Pressable></View>
          <ScrollView contentContainerStyle={{ gap: 10 }}>
            {picker === 'team' ? teams.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`${item.name} 경기 필터`} accessibilityState={{ selected: team === item.id }}
              onPress={() => { setTeam(item.id); setSelectedMonth(null); setPicker(null); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 54, borderRadius: 18, padding: 14, backgroundColor: team === item.id ? colors.line : colors.bg }}>
              <TeamCharacter teamId={item.id} size={44} />
              <Text style={[s.heading, { fontSize: 17, color: team === item.id ? colors.ink : colors.ink }]}>{item.name}{team === item.id ? '  ✓' : ''}</Text>
            </Pressable>) : <YearMonthPicker year={season} month={month} availableMonths={availableMonths} onChange={(_, value) => { setSelectedMonth(value); setPicker(null); }} />}
          </ScrollView>
        </View>
      </View>
    </Modal>
  </>;
}
