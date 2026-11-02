import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

export function sanitizeBuilds(builds, sha, platform) {
  assert.match(sha ?? '', /^[a-f0-9]{40}$/);
  assert.ok(['ios', 'android'].includes(platform));
  assert.ok(Array.isArray(builds) && builds.length === 1, 'Expected one platform build');
  return builds.map(build => {
    assert.equal(build.status, 'FINISHED', 'EAS build did not finish successfully');
    assert.equal(build.gitCommitHash, sha, 'EAS build commit does not match validated CI');
    assert.equal(build.platform.toLowerCase(), platform);
    assert.equal(build.distribution, 'STORE');
    assert.equal(build.buildProfile, 'production');
    assert.match(build.id, /^[a-f0-9-]{36}$/);
    // Never retain signed download/log URLs, which may contain temporary credentials.
    return { id: build.id, platform: build.platform, status: build.status, gitCommitHash: build.gitCommitHash,
      distribution: build.distribution, buildProfile: build.buildProfile, appVersion: build.appVersion,
      appBuildVersion: build.appBuildVersion, createdAt: build.createdAt };
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [input, output] = process.argv.slice(2);
  const result = sanitizeBuilds(JSON.parse(await readFile(input, 'utf8')), process.env.GITHUB_SHA, process.env.RELEASE_PLATFORM);
  await writeFile(output, JSON.stringify(result, null, 2) + '\n');
  console.log(`Verified ${result[0].platform} store build ${result[0].id}`);
}
