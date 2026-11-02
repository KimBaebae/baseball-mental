import assert from 'node:assert/strict';
import { test } from 'node:test';
import { requireSuccessfulCI } from './require-ci.mjs';
import { sanitizeBuilds } from './build-metadata.mjs';
const sha = 'a'.repeat(40);
const run = { id: 1, head_sha: sha, head_branch: 'main', event: 'push', run_number: 1, status: 'completed', conclusion: 'success', html_url: 'https://github.com/test/repo/actions/runs/1' };
const options = (runs, jobs) => ({ repository: 'test/repo', sha, token: 'test-only', request: async url => ({ ok: true, status: 200, json: async () => url.includes('/jobs?') ? { jobs } : { workflow_runs: runs } }) });
const successfulJobs = [{ name: 'mobile', conclusion: 'success' }, { name: 'server', conclusion: 'success' }];
test('release requires exact commit and both successful jobs', async () => {
  assert.equal(await requireSuccessfulCI(options([run], successfulJobs)), run.html_url);
  await assert.rejects(requireSuccessfulCI(options([{ ...run, head_sha: 'b'.repeat(40) }], successfulJobs)), /No push CI/);
  await assert.rejects(requireSuccessfulCI(options([run], [{ name: 'mobile', conclusion: 'success' }, { name: 'server', conclusion: 'skipped' }])), /server job must succeed/);
});
test('a newer pending or failed validation cannot use an older success', async () => {
  await assert.rejects(requireSuccessfulCI(options([run, { ...run, id: 2, run_number: 2, status: 'in_progress', conclusion: null }], successfulJobs)), /CI is still running/);
  await assert.rejects(requireSuccessfulCI(options([{ ...run, conclusion: 'failure' }], successfulJobs)), /Latest validation run/);
});
const build = { id: '11111111-1111-1111-1111-111111111111', status: 'FINISHED', gitCommitHash: sha, platform: 'IOS', distribution: 'STORE', buildProfile: 'production', artifacts: { buildUrl: 'https://example.com?secret=secret' } };
test('metadata excludes signed URLs and rejects wrong commit/platform/non-store builds', () => {
  assert.equal(JSON.stringify(sanitizeBuilds([build], sha, 'ios')).includes('secret'), false);
  assert.throws(() => sanitizeBuilds([{ ...build, gitCommitHash: 'b'.repeat(40) }], sha, 'ios'), /commit/);
  assert.throws(() => sanitizeBuilds([build], sha, 'android'));
  assert.throws(() => sanitizeBuilds([{ ...build, distribution: 'INTERNAL' }], sha, 'ios'));
  assert.throws(() => sanitizeBuilds([{ ...build, status: 'ERRORED' }], sha, 'ios'), /did not finish/);
});
