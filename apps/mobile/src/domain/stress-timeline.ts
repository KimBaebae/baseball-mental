import type { MentalIndex } from '../api/games';
export type StressEvent = MentalIndex['events'][number];
export function groupStressEvents(events: StressEvent[]) {
  const innings = new Map<number, { top: StressEvent[]; bottom: StressEvent[] }>();
  for (const event of events) {
    if (!innings.has(event.inning)) innings.set(event.inning, { top: [], bottom: [] });
    innings.get(event.inning)![event.half].push(event);
  }
  return [...innings.entries()].sort(([a], [b]) => a - b).flatMap(([inning, halves]) => {
    const present = (['top', 'bottom'] as const).filter(half => halves[half].length);
    return present.map((half, index) => ({ key: `${inning}-${half}`, inning, half, firstInningSection: index === 0, data: halves[half] }));
  });
}
export const stressChange = (delta: number) => `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${Math.abs(delta)}점`;
