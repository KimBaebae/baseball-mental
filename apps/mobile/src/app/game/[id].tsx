import { useState } from 'react';
import { ScrollView, Text, View, Share } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { games, summarize } from '../../domain/game';
import { Button, Card, colors, s } from '../../ui';
import { useTeamVisual } from '../../team-visual';

export default function Game() {
  const visual = useTeamVisual();
  const { id } = useLocalSearchParams<{ id: string }>();
  const game = games.find(item => item.id === id);
  const [count, setCount] = useState(0);
  const [error, setError] = useState('');
  if (!game) return <View style={s.content}><Text style={s.heading}>경기를 찾을 수 없어요.</Text></View>;
  const plays = game.plays.slice(0, count);
  const result = summarize(plays);
  const label = result.level >= 70 ? '잠깐, 심호흡이 필요해요' : result.level >= 40 ? '조금씩 끓어오르는 중' : '아직은 평온한 마음';
  return <ScrollView style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content}>
    <Text style={s.eyebrow}>가상 경기 · {game.home} 응원</Text>
    <Text style={s.title}>{game.away} vs {game.home}</Text>
    <Card>
      <Text style={s.body}>내 멘탈 온도 · 의학적 지표가 아닌 재미용 점수</Text>
      <Text style={{ fontSize: 68, fontFamily: 'BagelFatOne', color: result.level >= 70 ? colors.orange : colors.green }}>{result.level}<Text style={{ fontSize: 20 }}> / 100</Text></Text>
      <View accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: result.level }} accessibilityLabel="멘탈 온도" style={{ height: 16, backgroundColor: colors.line, borderRadius: 8, overflow: 'hidden' }}>
        <View style={{ height: 16, width: `${result.level}%`, backgroundColor: result.level >= 70 ? colors.orange : colors.green }} />
      </View>
      <Text style={s.heading}>{label}</Text>
      <Text style={s.body}>기본 30점 · 누적 변화 {result.raw > 0 ? '+' : ''}{result.raw}점</Text>
    </Card>
    <Button title={count === game.plays.length ? '샘플 재생 완료' : '다음 샘플 이벤트 반영'} disabled={count === game.plays.length} onPress={() => setCount(value => Math.min(value + 1, game.plays.length))} />
    <Text style={s.body}>이 버튼은 자동 경기 이벤트가 들어오는 상황을 재현합니다. 실제 서비스의 수동 기록 기능이 아닙니다.</Text>
    {plays.length === 0 ? <Text style={s.body}>아직 반영된 이벤트가 없어요.</Text> : plays.map((play, index) => <Card key={play.id}>
      <Text style={s.eyebrow}>{play.inning}회 · {play.outs}아웃 · 주자 {play.runners}명</Text>
      <Text style={s.heading}>{play.label}</Text>
      <Text style={{ color: result.deltas[index] > 0 ? colors.orange : colors.green, fontSize: 22, fontWeight: '800' }}>{result.deltas[index] > 0 ? '+' : ''}{result.deltas[index]}점</Text>
    </Card>)}
    <Button title="샘플 결과 공유" onPress={() => { void Share.share({ message: `[가상 경기 체험] ${game.home} 응원 멘탈 온도 ${result.level}/100 · 왜저럴까` }).catch(() => setError('공유를 열지 못했어요. 다시 시도해주세요.')); }} />
    {error ? <Text style={s.body}>{error}</Text> : null}
    <Button title="처음부터 다시 보기" onPress={() => { setCount(0); setError(''); }} />
  </ScrollView>;
}
