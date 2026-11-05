import { ActivityIndicator, Text, View } from 'react-native';
import { Redirect } from 'expo-router';
import { TeamChooser } from '../TeamChooser';
import { useTeamPreference } from '../team-preference';
import { Button, colors, s } from '../ui';

export default function Home() {
  const { teamId, status, reload } = useTeamPreference();
  if (status === 'loading') return <View style={[s.page, { justifyContent: 'center' }]}><ActivityIndicator accessibilityLabel="응원팀 불러오는 중" color={colors.ink} /></View>;
  if (status === 'error') return <View style={[s.page, s.content]}><Text style={s.heading}>응원팀 정보를 불러오지 못했어요.</Text><Button title="다시 시도" onPress={reload} /></View>;
  if (!teamId) return <TeamChooser />;
  return <Redirect href="/season" />;
}
