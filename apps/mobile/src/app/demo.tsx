import { router } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';
import { games } from '../domain/game';
import { Button, Card, s } from '../ui';
import { appearance as visual } from '../theme';

export default function Demo() {
  return <ScrollView style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content}>
    <Text style={s.title}>가상 경기 체험</Text>
    <Text style={s.body}>아래는 실제 일정·선수 기록이 아닌 화면 체험용 경기예요.</Text>
    {games.map(game => <Card key={game.id}>
      <View style={s.row}><Text style={s.eyebrow}>DEMO · {game.inning}</Text><Text style={s.body}>{game.note}</Text></View>
      <Text style={s.heading}>{game.away}   {game.score}   {game.home}</Text>
      <Text style={s.body}>{game.home} 응원 시점의 샘플 시나리오</Text>
      <Button title="멘탈 기록 열기 →" onPress={() => router.push({ pathname: '/game/[id]', params: { id: game.id } })} />
    </Card>)}
    <Text style={s.body}>가상 경기 기록은 앱을 종료하면 초기화돼요.</Text>
  </ScrollView>;
}
