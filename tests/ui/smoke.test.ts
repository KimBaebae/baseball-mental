import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { test } from 'node:test';
import { remote } from 'webdriverio';

const platform = process.env.UI_PLATFORM;
if (platform !== 'ios' && platform !== 'android') {
  throw new Error('Set UI_PLATFORM=ios or android');
}
const udid = process.env.UI_UDID;
if (!udid) throw new Error('Set UI_UDID to the intended simulator/emulator ID');
const appId = 'com.kimbaebae.baseballmental';
const artifacts = path.resolve('artifacts/ui', `${platform}-${Date.now()}`);

test(`${platform}: home → game → stress events`, { timeout: 240_000 }, async () => {
  await mkdir(artifacts, { recursive: true });
  const driver = await remote({
    hostname: '127.0.0.1', port: Number(process.env.APPIUM_PORT ?? 4723),
    logLevel: 'warn', connectionRetryCount: 0, connectionRetryTimeout: 180_000,
    capabilities: {
      platformName: platform === 'ios' ? 'iOS' : 'Android',
      'appium:automationName': platform === 'ios' ? 'XCUITest' : 'UiAutomator2',
      'appium:udid': udid,
      'appium:noReset': true,
      ...(platform === 'ios' ? {
        'appium:bundleId': appId,
        'appium:wdaLaunchTimeout': 120_000,
      } : {
        'appium:appPackage': appId,
        'appium:appActivity': '.MainActivity',
        'appium:autoLaunch': false,
        'appium:uiautomator2ServerLaunchTimeout': 90_000,
      }),
    },
  });
  // Visible labels keep the same scenario on both platforms. No screen coordinates.
  const label = (text: string) => platform === 'ios'
    ? `-ios predicate string:label == ${JSON.stringify(text)} AND accessible == true`
    : `android=new UiSelector().text(${JSON.stringify(text)})`;
  const accessible = (text: string) => platform === 'ios' ? label(text) : `~${text}`;
  async function visible(text: string, first = false, timeout = 15_000) {
    const selector = label(text);
    if (first) {
      await driver.waitUntil(async () => (await driver.$$(selector)).length > 0, { timeout });
    }
    const element = first ? await driver.$$(selector)[0] : await driver.$(selector);
    await element.waitForDisplayed({ timeout });
    return element;
  }
  try {
    await driver.terminateApp(appId);
    await driver.activateApp(appId);
    const teamChoice = platform === 'ios'
      ? '-ios predicate string:label == "두산 선택" AND accessible == true'
      : '~두산 선택';
    await driver.waitUntil(async () => (await driver.$(teamChoice)).isExisting() || (await driver.$(accessible('설정 열기'))).isExisting(), { timeout: 30_000 });
    if (await (await driver.$(teamChoice)).isExisting()) {
      await (await driver.$(teamChoice)).click();
      await (await visible('이 팀으로 시작')).click();
      await visible('두산 팬의 관전석');
      await driver.terminateApp(appId);
      await driver.activateApp(appId);
      await visible('두산 팬의 관전석');
    }
    await (await driver.$(accessible('설정 열기'))).click();
    await (await visible('가상 경기 체험')).click();
    await (await visible('멘탈 기록 열기 →', true)).click();
    await visible('LG vs 두산');
    // Fixed product expectations: do not import the implementation's scoring function.
    const scores = [30, 44, 67, 33, 65];
    for (let index = 0; index < scores.length; index++) {
      await visible(`${scores[index]} / 100`);
      if (index < scores.length - 1) {
        await (await visible('다음 샘플 이벤트 반영')).click();
      }
    }
    const completed = await visible('샘플 재생 완료');
    // Android text is inside the disabled Pressable; inspect its accessible button.
    const button = platform === 'android'
      ? await driver.$('~샘플 재생 완료') : completed;
    assert.equal(await button.isEnabled(), false, 'Replay must be disabled when complete');
    if (process.env.UI_VERIFY_SEASON === '1') {
      await driver.terminateApp(appId);
      await driver.activateApp(appId);
      await driver.waitUntil(async () => (await driver.$(accessible('설정 열기'))).isExisting(), { timeout: 120_000 });
      await (await driver.$(accessible('연도와 월 선택'))).click();
      await visible('3월');
      assert.equal(await (await driver.$(label('2월'))).isExisting(), false, 'Offseason month must be hidden');
      await (await driver.$(accessible('선택 닫기'))).click();
      const currentTeamFilter = platform === 'ios'
        ? '-ios predicate string:label ENDSWITH "경기 필터" AND accessible == true'
        : 'android=new UiSelector().descriptionContains("경기 필터")';
      await (await driver.$(currentTeamFilter)).click();
      await (await driver.$(accessible('LG 경기 필터'))).waitForDisplayed();
    }
    await driver.saveScreenshot(path.join(artifacts, 'passed.png'));
    await writeFile(path.join(artifacts, 'result.json'), JSON.stringify({ platform, udid, passed: true, scores, verifiedSeason: process.env.UI_VERIFY_SEASON === '1' }, null, 2));
  } catch (error) {
    await Promise.allSettled([
      driver.saveScreenshot(path.join(artifacts, 'failed.png')),
      driver.getPageSource().then(xml => writeFile(path.join(artifacts, 'failed.xml'), xml)),
      writeFile(path.join(artifacts, 'error.txt'), String(error)),
    ]);
    throw error;
  } finally {
    await driver.deleteSession();
    console.log(`UI artifacts: ${artifacts}`);
  }
});
