import type { SeasonGame } from '../api/games';

export function seasonMonths(games: SeasonGame[]): number[] {
  const months = games.map(game => Number(game.game_date.slice(5, 7))).filter(month => month >= 3 && month <= 11);
  if (!months.length) return Array.from({ length: 9 }, (_, index) => index + 3);
  return Array.from({ length: Math.max(...months) - 2 }, (_, index) => index + 3);
}

export function latestCompletedMonth(games: SeasonGame[]): number | null {
  const months = games.filter(game => game.status === 'completed').map(game => Number(game.game_date.slice(5, 7))).filter(month => month >= 3 && month <= 11);
  return months.length ? Math.max(...months) : null;
}
