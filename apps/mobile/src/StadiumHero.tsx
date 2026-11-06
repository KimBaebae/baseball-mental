import type { PropsWithChildren } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { theme } from './theme';

// Decorative shared artwork, not a photo of the selected game's venue.
export function StadiumHero({ children, compact = false }: PropsWithChildren<{ compact?: boolean }>) {
  return <View style={styles.hero}>
    <Image source={require('../assets/stadium/dusk-concept.jpg')} resizeMode="cover" style={[styles.image, { height: compact ? 190 : 240 }]} accessible={false} />
    <View style={styles.content}>
      <Text style={styles.caption}>구장 콘셉트 이미지</Text>
      {children}
    </View>
  </View>;
}

const styles = StyleSheet.create({
  hero: { marginHorizontal: -theme.spacing.page, backgroundColor: theme.colors.bg },
  image: { width: '100%' },
  content: { marginTop: -30, paddingHorizontal: theme.spacing.page, paddingBottom: 10, gap: 12 },
  caption: { color: theme.colors.muted, fontSize: 11, textAlign: 'right' },
});
