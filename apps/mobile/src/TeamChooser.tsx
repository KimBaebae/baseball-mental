import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { teams } from './domain/teams';
import { useTeamPreference } from './team-preference';
import { Button, Card, colors, s } from './ui';

export function TeamChooser({ onSaved }: { onSaved?: () => void }) {
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

  return <ScrollView style={s.page} contentContainerStyle={s.content}>
    <Text style={s.eyebrow}>우리 팀부터 정해볼까요</Text>
    <Text style={s.title}>{'어느 팀 때문에\n마음이 바쁠까요?'}</Text>
    <Text style={s.body}>응원팀을 고르면 지난 경기를 우리 팀 관점으로 먼저 보여드려요. 다른 팀의 경기도 볼 수 있고, 선택은 언제든 바꿀 수 있어요.</Text>
    <Card>
      <Text style={s.heading}>응원팀 선택</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {teams.map(team => <Pressable key={team.id} accessibilityRole="button" accessibilityLabel={`${team.name} 선택`}
          accessibilityState={{ selected: choice === team.id }} onPress={() => setChoice(team.id)}
          style={{ minWidth: '46%', minHeight: 62, padding: 16, borderWidth: 1, borderRadius: 18,
            borderColor: choice === team.id ? colors.green : colors.line,
            backgroundColor: choice === team.id ? colors.surface : colors.bg, justifyContent: 'center' }}>
          <Text style={{ color: choice === team.id ? colors.ink : colors.muted, fontSize: 18, fontWeight: '700' }}>
            {choice === team.id ? '✓ ' : ''}{team.name}
          </Text>
        </Pressable>)}
      </View>
    </Card>
    {error ? <Text accessibilityRole="alert" style={s.body}>{error}</Text> : null}
    <Button title={teamId ? '응원팀 변경하기' : '이 팀으로 시작'} disabled={!choice || busy} onPress={() => { void save(); }} />
    <Text style={s.body}>이 선택은 현재 기기에 저장돼요. 로그인·기기 간 동기화는 아직 준비 중이에요.</Text>
  </ScrollView>;
}
