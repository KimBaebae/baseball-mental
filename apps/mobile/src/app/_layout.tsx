import { Stack, router } from 'expo-router';
import { useEffect } from 'react';
import { ActivityIndicator, Platform, View } from 'react-native';
import { useFonts } from 'expo-font';
import { StatusBar } from 'expo-status-bar';
import { colors } from '../ui';
import { games } from '../domain/game';
import { TeamPreferenceProvider, useTeamPreference } from '../team-preference';
import { appearance as visual } from '../theme';
import type { NotificationResponse } from 'expo-notifications';

export default function Layout() {
  return <TeamPreferenceProvider><AppShell /></TeamPreferenceProvider>;
}

function AppShell() {
  const [fontsLoaded, fontError] = useFonts({ BagelFatOne: require('../../assets/fonts/BagelFatOne-Regular.ttf') });
  const { teamId, status } = useTeamPreference();
  useEffect(() => {
    if (Platform.OS === 'web') return;
    let cleanup: (() => void) | undefined;
    let active = true;
    void import('expo-notifications').then(N => {
      if (!active) return;
      N.setNotificationHandler({ handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }) });
      const open = (response: NotificationResponse | null) => {
        const id = response?.notification.request.content.data?.gameId;
        if (typeof id === 'string' && games.some(game => game.id === id)) {
          router.push({ pathname: '/game/[id]', params: { id } });
          void N.clearLastNotificationResponseAsync();
        }
      };
      const sub = N.addNotificationResponseReceivedListener(open);
      cleanup = () => sub.remove();
      void N.getLastNotificationResponseAsync().then(response => { if (active) open(response); }).catch(() => {});
    }).catch(() => {});
    return () => { active = false; cleanup?.(); };
  }, []);
  if (!fontsLoaded && !fontError) return <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: 'center' }}><StatusBar style="light" /><ActivityIndicator accessibilityLabel="화면 준비 중" color={colors.ink} /></View>;
  return <><StatusBar style="light" /><Stack screenOptions={{ headerStyle: { backgroundColor: visual.soft }, headerTintColor: colors.ink, headerShadowVisible: false, headerTitleStyle: { fontFamily: 'BagelFatOne', fontSize: 22 }, contentStyle: { backgroundColor: visual.soft } }}>
    <Stack.Screen name="index" options={{ title: '왜저럴까' }} />
    <Stack.Protected guard={status === 'ready' && !!teamId} redirectTo="/">
      <Stack.Screen name="team" options={{ headerShown: false, presentation: 'fullScreenModal' }} />
      <Stack.Screen name="settings" options={{ title: '설정' }} />
      <Stack.Screen name="demo" options={{ title: '가상 경기 체험' }} />
      <Stack.Screen name="game/[id]" options={{ title: '오늘의 스트레스' }} />
      <Stack.Screen name="season/index" options={{ title: '2026 지난 경기' }} />
      <Stack.Screen name="season/[id]" options={{ title: '경기 스트레스 지수' }} />
      <Stack.Screen name="records/index" options={{ title: '서버 경기 기록' }} />
      <Stack.Screen name="records/[id]" options={{ title: '서버 경기 상세' }} />
      <Stack.Screen name="notifications" options={{ title: '알림 검증' }} />
    </Stack.Protected>
  </Stack></>;
}
