import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { router } from 'expo-router';
import { games } from '../domain/game';
import { teamName } from '../domain/teams';
import { TeamChooser } from '../TeamChooser';
import { useTeamPreference } from '../team-preference';
import { Button, Card, colors, s } from '../ui';

export default function Home() {
  const { teamId, status, reload } = useTeamPreference();
  if (status === 'loading') return <View style={[s.page, { justifyContent: 'center' }]}><ActivityIndicator accessibilityLabel="응원팀 불러오는 중" color={colors.ink} /></View>;
  if (status === 'error') return <View style={[s.page, s.content]}><Text style={s.heading}>응원팀 정보를 불러오지 못했어요.</Text><Button title="다시 시도" onPress={reload} /></View>;
  if (!teamId) return <TeamChooser />;
  return <ScrollView style={s.page} contentContainerStyle={s.content}>
    <Text style={s.eyebrow}>{teamId ? `${teamName(teamId)} 팬의 관전석` : 'BASEBALL, WITH FEELINGS'}</Text>
    <Text style={s.title}>{'오늘도 야구,\n내 멘탈은 안녕?'}</Text>
    <Button title="응원팀 바꾸기" onPress={() => router.push('/team')} />
    <Button title="2026 지난 경기 멘탈지수" onPress={() => router.push('/season')} />
    <Text style={s.body}>지난 경기를 팀 관점으로 살펴보세요. 아래는 가상 경기 체험이에요.</Text>
    <Text style={s.body}>가상 경기로 화면 이동과 멘탈 변화를 체험해보세요. 실제 일정·중계·선수 기록이 아닙니다.</Text>
    {games.map(game => <Card key={game.id}>
      <View style={s.row}><Text style={s.eyebrow}>DEMO · {game.inning}</Text><Text style={s.body}>{game.note}</Text></View>
      <Text style={s.heading}>{game.away}   {game.score}   {game.home}</Text>
      <Text style={s.body}>{game.home} 응원 시점의 샘플 시나리오</Text>
      <Button title="멘탈 기록 열기 →" onPress={() => router.push({ pathname: '/game/[id]', params: { id: game.id } })} />
    </Card>)}
    <Button title="서버 경기 기록 조회" onPress={() => router.push('/records')} />
    <Button title="알림·푸시 검증" onPress={() => router.push('/notifications')} />
    <Text style={s.body}>가상 경기 기록은 앱을 종료하면 초기화돼요. 응원팀 선택은 이 기기에 저장돼요.</Text>
  </ScrollView>;
}
