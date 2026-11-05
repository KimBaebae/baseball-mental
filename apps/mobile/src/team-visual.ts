import { useTeamPreference } from './team-preference';

// App-authored color interpretations and Unicode characters, not club artwork.
export const teamVisuals: Record<string, { emoji: string; accent: string; soft: string }> = {
  LG: { emoji: '🦊🦊', accent: '#C53B54', soft: '#3B222B' },
  OB: { emoji: '🐻', accent: '#7794C2', soft: '#222D3D' },
  KT: { emoji: '🧙', accent: '#D25356', soft: '#382426' },
  SS: { emoji: '🦁', accent: '#5C9BE6', soft: '#20334A' },
  HH: { emoji: '🦅', accent: '#F19443', soft: '#3F2D20' },
  HT: { emoji: '🐯', accent: '#E85B5E', soft: '#3F2527' },
  LT: { emoji: '🧢', accent: '#8CA7D8', soft: '#26334A' },
  NC: { emoji: '🦕', accent: '#5CAACB', soft: '#203C48' },
  SK: { emoji: '🚀', accent: '#E46970', soft: '#40252A' },
  WO: { emoji: '🦸', accent: '#B484C9', soft: '#3A2841' },
};

export function useTeamVisual(teamId?: string | null) {
  const preference = useTeamPreference();
  return teamVisuals[teamId ?? preference.teamId ?? ''] ?? { emoji: '⚾', accent: '#F6F1DF', soft: '#202620' };
}
