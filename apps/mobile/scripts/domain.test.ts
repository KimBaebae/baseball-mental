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
