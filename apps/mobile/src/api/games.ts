export type GameSnapshot = {
  game_id: string;
  game_date: string;
  series_id: string;
  away_team_id: string;
  home_team_id: string;
  away_runs: number;
  home_runs: number;
  collected_at: string;
  source: 'kbo-public-probe';
  verification: 'historical-response-only';
  relay_line_count: number;
  content_hash: string;
};

export function validGameDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}

export function parseSnapshot(value: unknown): GameSnapshot {
  if (!value || typeof value !== 'object') throw new Error('경기 응답 형식이 올바르지 않아요.');
  const game = value as Record<string, unknown>;
  const textFields = ['game_id', 'game_date', 'series_id', 'away_team_id', 'home_team_id', 'collected_at', 'content_hash'];
  if (textFields.some(key => typeof game[key] !== 'string') ||
      !/^\d{8}[A-Z]{4}\d$/.test(String(game.game_id)) ||
      !validGameDate(String(game.game_date)) ||
      !Number.isFinite(Date.parse(String(game.collected_at))) ||
      !/(?:Z|[+-]\d{2}:\d{2})$/.test(String(game.collected_at)) ||
      !/^[a-f0-9]{64}$/.test(String(game.content_hash)) ||
      !['away_runs', 'home_runs'].every(key => Number.isInteger(game[key]) && Number(game[key]) >= 0) ||
      !Number.isInteger(game.relay_line_count) || Number(game.relay_line_count) <= 0 ||
      game.source !== 'kbo-public-probe' || game.verification !== 'historical-response-only') {
    throw new Error('경기 응답 형식이 올바르지 않아요.');
  }
  return value as GameSnapshot;
}

export function createGamesApi(baseUrl: string | undefined, request: typeof fetch = fetch, timeoutMs = 12_000) {
  async function get(route: string, signal?: AbortSignal): Promise<unknown> {
    if (!baseUrl?.trim()) throw new Error('경기 서버 연결이 아직 설정되지 않았어요.');
    let base: URL;
    try { base = new URL(baseUrl.trim()); } catch { throw new Error('경기 서버 주소 설정을 확인해주세요.'); }
    if (!['https:', 'http:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
      throw new Error('경기 서버 주소 설정을 확인해주세요.');
    }
    const controller = new AbortController();
    const cancel = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener('abort', cancel, { once: true });
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    try {
      const response = await request(`${base.href.replace(/\/$/, '')}${route}`, { signal: controller.signal, headers: { Accept: 'application/json' } });
      if (response.status === 404) throw new Error('경기 기록을 찾을 수 없어요.');
      if (response.status === 503) throw new Error('경기 서버가 아직 준비되지 않았어요. 잠시 후 다시 시도해주세요.');
      if (!response.ok) throw new Error('경기 기록을 불러오지 못했어요. 다시 시도해주세요.');
      try { return await response.json(); } catch { throw new Error('경기 응답 형식이 올바르지 않아요.'); }
    } catch (error) {
      if (timedOut) throw new Error('서버 응답이 늦어지고 있어요. 다시 시도해주세요.');
      if (signal?.aborted) throw error;
      if (error instanceof TypeError) throw new Error('서버에 연결할 수 없어요. 네트워크를 확인해주세요.');
      throw error;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
    }
  }
  return {
    async list(gameDate: string, signal?: AbortSignal): Promise<GameSnapshot[]> {
      if (!validGameDate(gameDate)) throw new Error('날짜를 YYYY-MM-DD 형식으로 입력해주세요.');
      const data = await get(`/v1/games?game_date=${encodeURIComponent(gameDate)}`, signal);
      if (!Array.isArray(data)) throw new Error('경기 목록 응답 형식이 올바르지 않아요.');
      const games = data.map(parseSnapshot);
      if (games.some(game => game.game_date !== gameDate)) throw new Error('요청한 날짜와 경기 기록이 일치하지 않아요.');
      return games;
    },
    async detail(id: string, signal?: AbortSignal): Promise<GameSnapshot> {
      if (!/^\d{8}[A-Z]{4}\d$/.test(id)) throw new Error('경기 ID가 올바르지 않아요.');
      const game = parseSnapshot(await get(`/v1/games/${encodeURIComponent(id)}`, signal));
      if (game.game_id !== id) throw new Error('요청한 경기와 기록이 일치하지 않아요.');
      return game;
    },
  };
}
