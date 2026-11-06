import { Image, View, type ImageSourcePropType } from 'react-native';
import { teamName } from './domain/teams';

const characters: Record<string, ImageSourcePropType> = {
  LG: require('../assets/team-characters/lg-doodle-v1.png'),
  OB: require('../assets/team-characters/ob-doodle-v1.png'),
  KT: require('../assets/team-characters/kt-doodle-v1.png'),
  SS: require('../assets/team-characters/ss-doodle-v1.png'),
  HH: require('../assets/team-characters/hh-doodle-v1.png'),
  HT: require('../assets/team-characters/ht-doodle-v1.png'),
  LT: require('../assets/team-characters/lt-doodle-v1.png'),
  NC: require('../assets/team-characters/nc-doodle-v1.png'),
  SK: require('../assets/team-characters/sk-doodle-v1.png'),
  WO: require('../assets/team-characters/wo-doodle-v1.png'),
};

export function TeamCharacter({ teamId, size = 56 }: { teamId: string; size?: number }) {
  const source = characters[teamId];
  if (!source) return null;
  return <View style={{ width: size, height: size, borderRadius: size * 0.2, backgroundColor: '#FFFFFF', padding: size * 0.04, overflow: 'hidden' }}>
    <Image source={source} resizeMode="contain" accessibilityLabel={`${teamName(teamId)} 시그니처 캐릭터`} style={{ width: '100%', height: '100%' }} />
  </View>;
}
