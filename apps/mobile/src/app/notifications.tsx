import { useState } from 'react';
import { Linking, Platform, ScrollView, Text } from 'react-native';
import Constants from 'expo-constants';
import { Button, Card, s } from '../ui';
import { appearance as visual } from '../theme';

export default function NotificationsScreen() {
  const [status, setStatus] = useState('아직 검증하지 않았어요.');
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const projectId = Constants.expoConfig?.extra?.eas?.projectId as string | undefined;
  const supported = Platform.OS !== 'web' && Constants.appOwnership !== 'expo';

  async function run(remote: boolean) {
    setBusy(true);
    try {
      if (!supported) throw new Error('알림은 전용 개발/미리보기 빌드에서 확인해주세요. 웹과 Expo Go는 이 검증에서 제외합니다.');
      if (remote && !projectId) throw new Error('Expo 프로젝트 연결이 필요해요. README의 계정 연결 단계를 진행해주세요.');
      const N = await import('expo-notifications');
      if (Platform.OS === 'android') await N.setNotificationChannelAsync('game-reminders', { name: '경기 알림', importance: N.AndroidImportance.HIGH });
      let permissions = await N.getPermissionsAsync();
      if (!permissions.granted) permissions = await N.requestPermissionsAsync();
      if (!permissions.granted && permissions.ios?.status !== N.IosAuthorizationStatus.PROVISIONAL) throw new Error('알림 권한이 꺼져 있어요. 기기 설정에서 허용한 뒤 다시 시도해주세요.');
      if (remote) {
        setToken((await N.getExpoPushTokenAsync({ projectId })).data);
        setStatus('푸시 토큰 발급 완료. 아직 원격 푸시 수신이 검증된 것은 아니에요. README의 발송 절차로 확인해주세요.');
      } else {
        await N.scheduleNotificationAsync({
          content: { title: '오늘은 마음을 단단히!', body: '[샘플 로컬 알림] 눌러서 경기 화면을 열어보세요.', data: { gameId: 'demo-1' }, sound: 'default' },
          trigger: { type: N.SchedulableTriggerInputTypes.TIME_INTERVAL, seconds: 5, channelId: 'game-reminders' },
        });
        setStatus('5초 뒤 로컬 알림을 예약했어요. 앱을 배경으로 보내고 수신·탭 이동을 확인해주세요. 원격 푸시 검증과는 별개예요.');
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '알림 처리에 실패했어요. 다시 시도해주세요.');
    } finally { setBusy(false); }
  }

  return <ScrollView style={[s.page, { backgroundColor: visual.soft }]} contentContainerStyle={s.content}>
    <Text style={s.eyebrow}>DEVICE CHECK</Text><Text style={s.title}>{'경기 전에,\n마음의 준비.'}</Text>
    <Card><Text style={s.heading}>1. 로컬 알림</Text><Text style={s.body}>권한 요청과 알림을 눌렀을 때 경기 화면으로 이동하는 흐름을 확인해요.</Text><Button disabled={busy || !supported} title="5초 뒤 테스트 알림" onPress={() => { void run(false); }} /></Card>
    <Card><Text style={s.heading}>2. 원격 푸시</Text><Text style={s.body}>Expo 프로젝트와 APNs/FCM 자격 증명 설정 후 확인해요. 토큰 발급만으로 수신 성공으로 판단하지 않아요.</Text><Button disabled={busy || !supported} title="이 기기의 푸시 토큰 받기" onPress={() => { void run(true); }} /></Card>
    {!supported ? <Text style={s.body}>화면 미리보기 모드입니다. 알림은 전용 빌드를 설치한 후 확인해주세요.</Text> : null}
    <Text accessibilityLiveRegion="polite" style={s.body}>{status}</Text>
    {token ? <Card><Text style={s.heading}>테스트 기기 토큰</Text><Text selectable style={s.body}>{token}</Text><Text style={s.body}>공개 저장소·스크린샷에 올리지 마세요. 테스트 발송에만 사용해요.</Text></Card> : null}
    {Platform.OS !== 'web' ? <Button title="기기 알림 설정 열기" onPress={() => { void Linking.openSettings().catch(() => setStatus('설정 앱을 직접 열어주세요.')); }} /> : null}
  </ScrollView>;
}
