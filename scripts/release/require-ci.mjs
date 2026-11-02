import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

export async function requireSuccessfulCI({ repository, sha, token, request = fetch }) {
  assert.match(repository ?? '', /^[\w.-]+\/[\w.-]+$/, 'Invalid GitHub repository');
  assert.match(sha ?? '', /^[a-f0-9]{40}$/, 'Expected a full commit SHA');
  assert.ok(token, 'GH_TOKEN is required');
  const api = async route => {
    const response = await request(`https://api.github.com/repos/${repository}/${route}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' },
    });
    assert.ok(response.ok, `GitHub API failed (${response.status})`);
    return response.json();
  };
  const { workflow_runs: runs } = await api(`actions/workflows/check.yml/runs?head_sha=${sha}&event=push&per_page=100`);
  const run = runs.filter(item => item.head_sha === sha && item.head_branch === 'main' && item.event === 'push')
    .sort((a, b) => b.run_number - a.run_number)[0];
  assert.ok(run, 'No push CI run for this main commit. Run validation first.');
  assert.equal(run.status, 'completed', 'CI is still running; retry release after it completes');
  assert.equal(run.conclusion, 'success', 'Latest validation run must succeed');
  const { jobs } = await api(`actions/runs/${run.id}/jobs?filter=latest&per_page=100`);
  for (const name of ['mobile', 'server']) {
    assert.ok(jobs.some(job => job.name === name && job.conclusion === 'success'), `${name} job must succeed, not be skipped`);
  }
  return run.html_url;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const url = await requireSuccessfulCI({ repository: process.env.GITHUB_REPOSITORY, sha: process.env.GITHUB_SHA, token: process.env.GH_TOKEN });
  console.log(`Validated same-commit CI: ${url}`);
}
