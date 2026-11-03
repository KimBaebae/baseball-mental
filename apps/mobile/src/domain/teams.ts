export const teams = [
  { id: 'LG', name: 'LG' }, { id: 'OB', name: '두산' }, { id: 'KT', name: 'KT' },
  { id: 'SS', name: '삼성' }, { id: 'HH', name: '한화' }, { id: 'HT', name: 'KIA' },
  { id: 'LT', name: '롯데' }, { id: 'NC', name: 'NC' }, { id: 'SK', name: 'SSG' }, { id: 'WO', name: '키움' },
];
export const teamName = (id: string) => teams.find(team => team.id === id)?.name ?? id;
export const indexLabel = { ready: '지수 확인 가능', incomplete: '자료 확인 중', missing: '지수 준비 전' } as const;

export function mentalReason(reason: string | null, status: 'ready' | 'incomplete' | 'missing'): string {
  // Parser diagnostic codes are for operators, not the product's empty-state copy.
  if (reason && /[가-힣]/.test(reason)) return reason;
  return status === 'incomplete'
    ? '일부 경기 사건을 확인하지 못해 전체 지수를 표시하지 않아요. 자료를 확인하고 있어요.'
    : '이 경기의 지수를 계산할 자료가 아직 준비되지 않았어요.';
}

export function gameIdentity(id: unknown): { date: string; away: string; home: string } | null {
  if (typeof id !== 'string') return null;
  const match = /^(\d{4})(\d{2})(\d{2})([A-Z]{2})([A-Z]{2})\d$/.exec(id);
  if (!match) return null;
  const date = `${match[1]}-${match[2]}-${match[3]}`;
  if (!Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date ||
      !teams.some(team => team.id === match[4]) || !teams.some(team => team.id === match[5]) || match[4] === match[5]) return null;
  return { date, away: match[4], home: match[5] };
}
