import { SafeAreaView } from 'react-native-safe-area-context';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { TeamCharacter } from './TeamCharacter';
import { teams } from './domain/teams';
import { useTeamPreference } from './team-preference';
import { Button, Card, colors, s } from './ui';

export function TeamChooser({ onSaved, onCancel }: { onSaved?: () => void; onCancel?: () => void }) {
  const { teamId, selectTeam } = useTeamPreference();
  const [choice, setChoice] = useState(teamId ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    if (!choice || busy) return;
    setBusy(true);
    setError('');
    try {
      await selectTeam(choice);
      onSaved?.();
    } catch {
      setError('응원팀을 저장하지 못했어요. 다시 시도해주세요.');
    } finally {
      setBusy(false);
    }
  };

  return <SafeAreaView style={[s.page, { backgroundColor: colors.bg }]} edges={['top', 'bottom']}>
    <ScrollView contentContainerStyle={s.content}>
    {onCancel ? <Pressable accessibilityRole="button" accessibilityLabel="팀 변경 취소" onPress={onCancel} style={{ alignSelf: 'flex-end', padding: 10 }}><Text style={s.body}>닫기 ✕</Text></Pressable> : null}
    <Text style={s.eyebrow}>우리 팀부터 정해볼까요</Text>
    <Text style={s.title}>{'어느 팀 때문에\n마음이 바쁠까요?'}</Text>
    <Text style={s.body}>응원팀을 고르면 지난 경기를 우리 팀 관점으로 먼저 보여드려요. 다른 팀의 경기도 볼 수 있고, 선택은 언제든 바꿀 수 있어요.</Text>
    <Card>
      <Text style={s.heading}>응원팀 선택</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {teams.map(team => <Pressable key={team.id} accessibilityRole="button" accessibilityLabel={`${team.name} 선택`}
          accessibilityState={{ selected: choice === team.id }} onPress={() => setChoice(team.id)}
          style={{ minWidth: '46%', minHeight: 62, padding: 16, borderWidth: 1, borderRadius: 18,
            borderColor: choice === team.id ? colors.ink : colors.line,
            backgroundColor: choice === team.id ? colors.surface : colors.bg, justifyContent: 'center' }}>
          <TeamCharacter teamId={team.id} size={68} />
          <Text style={{ color: choice === team.id ? colors.ink : colors.muted, fontSize: 18, fontWeight: '700' }}>
            {choice === team.id ? '✓ ' : ''}{team.name}
          </Text>
        </Pressable>)}
      </View>
    </Card>
    <Text style={s.body}>선택은 언제든 설정에서 바꿀 수 있어요.</Text>
    </ScrollView>
    <View style={{ padding: 20, gap: 8 }}>
    {error ? <Text accessibilityRole="alert" style={s.body}>{error}</Text> : null}
    <Button title={teamId ? '저장하기' : '이 팀으로 시작'} disabled={!choice || busy} onPress={() => { void save(); }} />
    </View>
  </SafeAreaView>;
}
