import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { PropsWithChildren } from 'react';

import { theme } from './theme';
export const colors = theme.colors;
export function Button({ title, onPress, disabled = false }: { title: string; onPress: () => void; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [s.button, { opacity: disabled ? 0.4 : pressed ? 0.75 : 1 }]}><Text style={s.buttonText}>{title}</Text></Pressable>;
}
export function Card({ children }: PropsWithChildren) { return <View style={s.card}>{children}</View>; }
export const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.bg },
  content: { padding: theme.spacing.page, gap: theme.spacing.section, paddingBottom: 50, maxWidth: 600, width: '100%', alignSelf: 'center' },
  eyebrow: { color: colors.green, fontSize: 12, fontWeight: '800', letterSpacing: 2 },
  title: { color: colors.ink, fontSize: theme.type.title, fontFamily: 'BagelFatOne' },
  heading: { color: colors.ink, fontSize: theme.type.heading, fontWeight: '700' },
  body: { color: colors.muted, fontSize: theme.type.body, lineHeight: 23 },
  card: { paddingVertical: theme.spacing.page, gap: theme.spacing.item, borderBottomWidth: 1, borderColor: colors.line },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  button: { backgroundColor: colors.primary, borderRadius: theme.radius.control, padding: theme.spacing.control, alignItems: 'center', minHeight: 50 },
  buttonText: { color: colors.onPrimary, fontSize: theme.type.button, fontFamily: 'BagelFatOne', textAlign: 'center' },
});
