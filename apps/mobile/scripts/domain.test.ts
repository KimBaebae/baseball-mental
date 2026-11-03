import assert from 'node:assert/strict';
import test from 'node:test';
import { games, stressDelta, summarize } from '../src/domain/game.ts';

test('a late close-game bases-loaded out is more stressful than an early out', () => {
  const play = games[0].plays[3];
  assert.ok(stressDelta(play) > stressDelta({ ...play, inning: 1, outs: 0, runners: 0 }));
});
test('replaying the same event does not double count, and correction replaces it', () => {
  const play = games[0].plays[0];
  assert.deepEqual(summarize([play, play]), summarize([play]));
  const corrected = { ...play, baseStress: 0 };
  assert.equal(summarize([play, corrected]).raw, 0);
});
test('recovery reduces stress and clipping preserves raw history', () => {
  assert.ok(stressDelta(games[0].plays[2]) < 0);
  const huge = { ...games[0].plays[0], baseStress: 1000 };
  assert.equal(summarize([huge]).level, 100);
  assert.ok(summarize([huge]).raw > 100);
  assert.equal(summarize([{ ...huge, baseStress: -1000 }]).level, 0);
});


// API contract failures must never turn into sample games or an empty success.
import { createGamesApi, validGameDate } from '../src/api/games.ts';
const snapshot = {
  game_id: '20260901LGOB0', game_date: '2026-09-01', series_id: '0',
  away_team_id: 'LG', home_team_id: 'OB', away_runs: 3, home_runs: 1,
  collected_at: '2026-09-01T13:00:00Z', source: 'kbo-public-probe',
  verification: 'historical-response-only', relay_line_count: 475, content_hash: 'a'.repeat(64),
};
const respond = (body: unknown, status = 200): typeof fetch => async () => new Response(JSON.stringify(body), { status });

test('API builds date query, validates provenance, and preserves empty results', async () => {
  let requested = '';
  const api = createGamesApi('https://api.example.test/', async input => {
    requested = String(input); return new Response(JSON.stringify([snapshot]));
  });
  assert.deepEqual(await api.list('2026-09-01'), [snapshot]);
  assert.equal(requested, 'https://api.example.test/v1/games?game_date=2026-09-01');
  assert.deepEqual(await createGamesApi('https://api.example.test', respond([])).list('2026-09-01'), []);
  assert.equal(validGameDate('2026-02-30'), false);
});

test('API distinguishes not-ready and missing-game errors from empty data', async () => {
  await assert.rejects(createGamesApi('https://api.example.test', respond({}, 503)).list('2026-09-01'), /준비되지/);
  await assert.rejects(createGamesApi('https://api.example.test', respond({}, 404)).detail(snapshot.game_id), /찾을 수/);
  await assert.rejects(createGamesApi(undefined).list('2026-09-01'), /설정되지/);
});

test('API rejects malformed, mismatched and unverified responses', async () => {
  const run = (data: unknown) => createGamesApi('https://api.example.test', respond(data)).detail(snapshot.game_id);
  await assert.rejects(run({ ...snapshot, verification: 'live' }), /형식/);
  await assert.rejects(run({ ...snapshot, away_runs: -1 }), /형식/);
  await assert.rejects(run({ ...snapshot, game_id: '20260901HHKT0' }), /일치하지/);
  await assert.rejects(createGamesApi('https://api.example.test', respond([snapshot])).list('2026-09-02'), /날짜/);
});

test('API reports timeout and propagates cancellation', async () => {
  const pending: typeof fetch = async (_input, init) => new Promise((_resolve, reject) => {
    if (init?.signal?.aborted) { reject(new Error('aborted')); return; }
    init?.signal?.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  });
  await assert.rejects(createGamesApi('https://api.example.test', pending, 5).list('2026-09-01'), /늦어지고/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(createGamesApi('https://api.example.test', pending).list('2026-09-01', controller.signal), /aborted/);
});


const seasonGame = {
  game_id: '20260901LGOB0', game_date: '2026-09-01', season: 2026, series_id: '0',
  away_team_id: 'LG', home_team_id: 'OB', status: 'completed', away_runs: 3, home_runs: 1,
  venue: '잠실', index_status: 'ready',
};
const seasonResponse = { season: 2026, games: [seasonGame], coverage: { completed: 1, indexed: 1, incomplete: 0, missing: 0 } };
const mentalResponse = {
  game_id: seasonGame.game_id, team_id: 'LG', status: 'ready', reason: null,
  score: 42, peak_score: 56, raw_total: 12, model_version: 'kbo-mental-v1',
  events: [{ event_id: 'e1', inning: 1, half: 'top', outcome: 'out', delta: 12, score_after: 42, batter_name: '샘플 선수' }],
  computed_at: '2026-11-03T01:00:00Z', source_hash: 'a'.repeat(64),
};

test('season API filters by team and month without login or attendance inputs', async () => {
  let requested = '';
  const api = createGamesApi('https://api.example.test', async input => {
    requested = String(input); return new Response(JSON.stringify(seasonResponse));
  });
  assert.deepEqual(await api.season(2026, { team: 'LG', month: 9 }), seasonResponse);
  assert.equal(requested, 'https://api.example.test/v1/seasons/2026/games?team_id=LG&month=9');
  await assert.rejects(api.season(2026, { month: 13 }), /월/);
  await assert.rejects(api.season(2026, { team: 'HH' }), /일치/);
  await assert.rejects(api.season(2026, { month: 8 }), /일치/);
});

test('mental API preserves ready scores and rejects wrong team perspective', async () => {
  const api = createGamesApi('https://api.example.test', respond(mentalResponse));
  assert.deepEqual(await api.mental(seasonGame.game_id, 'LG'), mentalResponse);
  await assert.rejects(api.mental(seasonGame.game_id, 'OB'), /형식/);
  await assert.rejects(createGamesApi('https://api.example.test', respond({ ...mentalResponse, score: 101 })).mental(seasonGame.game_id, 'LG'), /형식/);
});

test('missing and incomplete mental indices remain null, never a fabricated zero', async () => {
  for (const status of ['missing', 'incomplete']) {
    const payload = { ...mentalResponse, status, reason: '자료 확인 중', score: null, peak_score: null, raw_total: null, events: [], computed_at: null, source_hash: null };
    const result = await createGamesApi('https://api.example.test', respond(payload)).mental(seasonGame.game_id, 'LG');
    assert.equal(result.score, null);
    assert.equal(result.status, status);
    await assert.rejects(createGamesApi('https://api.example.test', respond({ ...payload, score: 0 })).mental(seasonGame.game_id, 'LG'), /형식/);
  }
});


test('mental timeline accepts documented non-batting events and rejects unknown outcomes', async () => {
  for (const outcome of ['wild_pitch', 'passed_ball', 'balk', 'stolen_base', 'caught_stealing', 'fielders_choice', 'hit_by_pitch', 'sacrifice']) {
    const payload = { ...mentalResponse, events: [{ ...mentalResponse.events[0], outcome }] };
    assert.equal((await createGamesApi('https://api.example.test', respond(payload)).mental(seasonGame.game_id, 'LG')).events[0].outcome, outcome);
  }
  const payload = { ...mentalResponse, events: [{ ...mentalResponse.events[0], outcome: 'unknown-event' }] };
  await assert.rejects(createGamesApi('https://api.example.test', respond(payload)).mental(seasonGame.game_id, 'LG'), /형식/);
});

test('ready mental timeline preserves strikeout reach, triple play and neutral runner advances', async () => {
  const events = [
    { ...mentalResponse.events[0], event_id: 'reach', outcome: 'strikeout_reached', delta: -4, score_after: 26 },
    { ...mentalResponse.events[0], event_id: 'triple', outcome: 'triple_play', delta: 26, score_after: 52 },
    { ...mentalResponse.events[0], event_id: 'advance', outcome: 'runner_advance', delta: 0, score_after: 52 },
  ];
  const payload = { ...mentalResponse, score: 52, peak_score: 52, raw_total: 22, events };
  const result = await createGamesApi('https://api.example.test', respond(payload)).mental(seasonGame.game_id, 'LG');
  assert.equal(result.status, 'ready');
  assert.deepEqual(result.events, events);
  assert.equal(result.score, 52);
});


import { mentalReason } from '../src/domain/teams.ts';
test('parser diagnostic codes do not leak into user-facing missing-index copy', () => {
  assert.equal(mentalReason('runner_origin_mismatch', 'incomplete').includes('runner_origin'), false);
  assert.match(mentalReason(null, 'missing'), /준비되지/);
  assert.equal(mentalReason('아직 자료를 확인 중이에요.', 'incomplete'), '아직 자료를 확인 중이에요.');
});


import { gameIdentity } from '../src/domain/teams.ts';
test('game header derives only valid dates and registered matchups from game IDs', () => {
  assert.deepEqual(gameIdentity('20260328KTLG0'), { date: '2026-03-28', away: 'KT', home: 'LG' });
  for (const id of ['20260230KTLG0', '20260328ZZLG0', '20260328LGLG0', 'bad', undefined, ['20260328KTLG0']]) {
    assert.equal(gameIdentity(id), null);
  }
});


test('snapshot month query rejects invalid months and out-of-month data', async () => {
  let requested = '';
  const api = createGamesApi('https://api.example.test', async input => {
    requested = String(input); return new Response(JSON.stringify([snapshot]));
  });
  assert.equal((await api.listMonth(2026, 9)).length, 1);
  assert.equal(requested, 'https://api.example.test/v1/games?year=2026&month=9');
  await assert.rejects(api.listMonth(2026, 0), /연도와 월/);
  await assert.rejects(api.listMonth(2026, 9.5), /연도와 월/);
  await assert.rejects(api.listMonth(2026, 8), /일치/);
});
