// A single editorial theme. Team preference controls content, never appearance.
export const theme = {
  colors: {
    bg: '#111111', surface: '#20201F', ink: '#F4F1EA', muted: '#AAA69F',
    green: '#8DCEB4', primary: '#F4F1EA', onPrimary: '#111111', line: '#45433F', orange: '#E69067',
  },
  spacing: { page: 22, section: 22, item: 14, control: 16 },
  radius: { card: 0, control: 999 },
  type: { title: 32, heading: 20, body: 15, button: 16 },
} as const;

export const appearance = {
  accent: theme.colors.primary,
  soft: theme.colors.bg,
  surface: theme.colors.surface,
  secondary: theme.colors.ink,
  border: theme.colors.line,
} as const;
