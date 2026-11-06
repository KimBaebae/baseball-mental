import { TeamCharacter } from '../TeamCharacter';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { ScrollView, Text } from 'react-native';
import { teamName } from '../domain/teams';
import { useTeamPreference } from '../team-preference';
import { appearance as visual } from '../theme';
import { Button, Card, s } from '../ui';

export default function Settings() {
  const { teamId } = useTeamPreference();
  return <ScrollView style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content}>
    <Text style={[s.eyebrow, { color: visual.accent }]}>내 관전석</Text>
    <Text style={s.title}>설정</Text>
    <Card>
      <Text style={s.heading}>응원하는 팀</Text>
      <TeamCharacter teamId={teamId ?? ''} size={88} />
      <Text style={s.body}>{teamName(teamId ?? '')}</Text>
      <Button title="응원하는 팀 변경하기" onPress={() => router.push('/team')} />
    </Card>
    <Card>
      <Text style={s.heading}>앱 정보</Text>
      <Text style={s.body}>왜저럴까 · 버전 {Constants.expoConfig?.version ?? '1.0.0'}</Text>
      <Text style={s.body}>경기 기록으로 계산한 재미용 지수이며 실제 감정 측정값은 아니에요.</Text>
    </Card>
    <Card>
      <Text style={s.heading}>기능 체험</Text>
      <Button title="가상 경기 체험" onPress={() => router.push('/demo')} />
      <Button title="서버 경기 기록" onPress={() => router.push('/records')} />
      <Button title="알림·푸시 검증" onPress={() => router.push('/notifications')} />
    </Card>
  </ScrollView>;
}
