import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { PropsWithChildren } from 'react';

import { theme, appearance as visual } from './theme';
export const colors = theme.colors;
export function textOn(hex: string): string {
  const channels = [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16) / 255)
    .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722 > 0.18 ? colors.onPrimary : colors.ink;
}
export function Button({ title, onPress, disabled = false, accent }: { title: string; onPress: () => void; disabled?: boolean; accent?: string }) {
  const buttonColor = accent ?? visual.accent;
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [s.button, { backgroundColor: buttonColor, opacity: disabled ? 0.4 : pressed ? 0.75 : 1 }]}><Text style={[s.buttonText, { color: textOn(buttonColor) }]}>{title}</Text></Pressable>;
}
export function Card({ children }: PropsWithChildren) {
  return <View style={[s.card, { borderColor: visual.border }]}>{children}</View>;
}
export const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.bg },
  content: { padding: theme.spacing.page, gap: theme.spacing.section, paddingBottom: 50, maxWidth: 600, width: '100%', alignSelf: 'center' },
  eyebrow: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 2 },
  title: { color: colors.ink, fontSize: theme.type.title, fontFamily: 'BagelFatOne' },
  heading: { color: colors.ink, fontSize: theme.type.heading, fontFamily: 'BagelFatOne' },
  body: { color: colors.muted, fontSize: theme.type.body, lineHeight: 23 },
  card: { paddingVertical: theme.spacing.page, gap: theme.spacing.item, borderBottomWidth: 1, borderColor: colors.line },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  button: { backgroundColor: colors.primary, borderRadius: theme.radius.control, padding: theme.spacing.control, alignItems: 'center', minHeight: 50 },
  buttonText: { color: colors.onPrimary, fontSize: theme.type.button, fontFamily: 'BagelFatOne', textAlign: 'center' },
});
