import { useTeamPreference } from './team-preference';
import { teamPalettes, neutralPalette } from './domain/team-palettes';

export const teamVisuals = teamPalettes;

// Global appearance always follows the saved support team, never a browsing filter.
export function useTeamVisual() {
  const { teamId } = useTeamPreference();
  return teamPalettes[teamId ?? ''] ?? neutralPalette;
}
