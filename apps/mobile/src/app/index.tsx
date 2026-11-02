import { ScrollView, Text, View } from 'react-native';
import { router } from 'expo-router';
import { games } from '../domain/game';
import { Button, Card, s } from '../ui';

export default function Home() {
  return <ScrollView style={s.page} contentContainerStyle={s.content}>
    <Text style={s.eyebrow}>BASEBALL, WITH FEELINGS</Text>
    <Text style={s.title}>{'오늘도 야구,\n내 멘탈은 안녕?'}</Text>
    <Text style={s.body}>가상 경기로 화면 이동과 멘탈 변화를 체험해보세요. 실제 일정·중계·선수 기록이 아닙니다.</Text>
    {games.map(game => <Card key={game.id}>
      <View style={s.row}><Text style={s.eyebrow}>DEMO · {game.inning}</Text><Text style={s.body}>{game.note}</Text></View>
      <Text style={s.heading}>{game.away}   {game.score}   {game.home}</Text>
      <Text style={s.body}>{game.home} 응원 시점의 샘플 시나리오</Text>
      <Button title="멘탈 기록 열기 →" onPress={() => router.push({ pathname: '/game/[id]', params: { id: game.id } })} />
    </Card>)}
    <Button title="서버 경기 기록 조회" onPress={() => router.push('/records')} />
    <Button title="알림·푸시 검증" onPress={() => router.push('/notifications')} />
    <Text style={s.body}>기술 검증용 · 기록은 앱을 종료하면 초기화됩니다.</Text>
  </ScrollView>;
}
