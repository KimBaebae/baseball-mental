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
    async season(season: number, filters: { team?: string; date?: string } = {}, signal?: AbortSignal): Promise<SeasonGames> {
      if (!Number.isInteger(season) || season < 1982 || season > 2100) throw new Error('시즌을 확인해주세요.');
      if (filters.team && !validTeam(filters.team)) throw new Error('응원팀을 확인해주세요.');
      if (filters.date && (!validGameDate(filters.date) || !filters.date.startsWith(`${season}-`))) throw new Error('해당 시즌의 날짜를 YYYY-MM-DD 형식으로 입력해주세요.');
      const params = new URLSearchParams();
      if (filters.team) params.set('team_id', filters.team);
      if (filters.date) params.set('game_date', filters.date);
      const data = parseSeasonGames(await get(`/v1/seasons/${season}/games${params.size ? `?${params}` : ''}`, signal), season);
      if (data.games.some(game => (filters.date && game.game_date !== filters.date) || (filters.team && game.away_team_id !== filters.team && game.home_team_id !== filters.team))) throw new Error('조회 조건과 경기 기록이 일치하지 않아요.');
      return data;
    },
    async mental(id: string, team: string, signal?: AbortSignal): Promise<MentalIndex> {
      if (!/^\d{8}[A-Z]{4}\d$/.test(id) || !validTeam(team)) throw new Error('경기와 응원팀을 확인해주세요.');
      return parseMentalIndex(await get(`/v1/games/${encodeURIComponent(id)}/mental?team_id=${encodeURIComponent(team)}`, signal), id, team);
    },
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

export type IndexStatus = 'ready' | 'incomplete' | 'missing';
export type SeasonGame = {
  game_id: string; game_date: string; season: number; series_id: string;
  away_team_id: string; home_team_id: string;
  status: 'completed' | 'scheduled' | 'cancelled' | 'unknown';
  away_runs: number | null; home_runs: number | null; venue: string | null;
  index_status: IndexStatus;
};
export type SeasonGames = {
  season: number; games: SeasonGame[];
  coverage: { completed: number; indexed: number; incomplete: number; missing: number };
};
export type MentalIndex = {
  game_id: string; team_id: string; status: IndexStatus; reason: string | null;
  score: number | null; peak_score: number | null; raw_total: number | null;
  model_version: string;
  events: { event_id: string; inning: number; half: 'top' | 'bottom'; outcome: string; delta: number; score_after: number; batter_name: string | null }[];
  computed_at: string | null; source_hash: string | null;
};
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const nonnegativeInteger = (value: unknown) => Number.isInteger(value) && Number(value) >= 0;
const nullableText = (value: unknown) => value === null || typeof value === 'string';
const score = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100;
const validTeam = (value: unknown) => typeof value === 'string' && /^[A-Z]{2}$/.test(value);
const mentalOutcomes = new Set(['out', 'strikeout', 'double_play', 'triple_play', 'strikeout_reached', 'runner_advance', 'hit', 'walk', 'home_run', 'error', 'wild_pitch', 'passed_ball', 'balk', 'stolen_base', 'caught_stealing', 'fielders_choice', 'hit_by_pitch', 'sacrifice']);
const indexStatus = (value: unknown) => ['ready', 'incomplete', 'missing'].includes(String(value));

export function parseSeasonGames(value: unknown, season: number): SeasonGames {
  const invalid = () => new Error('시즌 경기 응답 형식이 올바르지 않아요.');
  if (!object(value) || value.season !== season || !Array.isArray(value.games) || !object(value.coverage)) throw invalid();
  if (!['completed', 'indexed', 'incomplete', 'missing'].every(key => nonnegativeInteger((value.coverage as Record<string, unknown>)[key]))) throw invalid();
  for (const game of value.games) {
    if (!object(game) || !/^\d{8}[A-Z]{4}\d$/.test(String(game.game_id)) || !validGameDate(String(game.game_date)) ||
        !String(game.game_date).startsWith(`${season}-`) || game.season !== season || typeof game.series_id !== 'string' ||
        !validTeam(game.away_team_id) || !validTeam(game.home_team_id) || game.away_team_id === game.home_team_id ||
        !['completed', 'scheduled', 'cancelled', 'unknown'].includes(String(game.status)) || !indexStatus(game.index_status) ||
        !nullableText(game.venue) || ![game.away_runs, game.home_runs].every(run => run === null || nonnegativeInteger(run))) throw invalid();
  }
  return value as SeasonGames;
}

export function parseMentalIndex(value: unknown, id: string, team: string): MentalIndex {
  const invalid = () => new Error('멘탈지수 응답 형식이 올바르지 않아요.');
  if (!object(value) || value.game_id !== id || value.team_id !== team || !indexStatus(value.status) ||
      !nullableText(value.reason) || typeof value.model_version !== 'string' || !Array.isArray(value.events) ||
      !(value.computed_at === null || (typeof value.computed_at === 'string' && Number.isFinite(Date.parse(value.computed_at)))) ||
      !(value.source_hash === null || (typeof value.source_hash === 'string' && /^[a-f0-9]{64}$/.test(value.source_hash)))) throw invalid();
  if (value.status === 'ready') {
    if (!score(value.score) || !score(value.peak_score) || typeof value.raw_total !== 'number' || !Number.isFinite(value.raw_total)) throw invalid();
  } else if (value.score !== null || value.peak_score !== null || value.raw_total !== null) throw invalid();
  for (const event of value.events) {
    if (!object(event) || typeof event.event_id !== 'string' || !Number.isInteger(event.inning) || Number(event.inning) < 1 ||
        !['top', 'bottom'].includes(String(event.half)) || !mentalOutcomes.has(String(event.outcome)) ||
        typeof event.delta !== 'number' || !Number.isFinite(event.delta) || !score(event.score_after) || !nullableText(event.batter_name)) throw invalid();
  }
  return value as MentalIndex;
}
