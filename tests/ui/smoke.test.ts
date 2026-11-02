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
const appId = 'com.baseballmentalpoc.app';
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
      }),
    },
  });
  // Visible labels keep the same scenario on both platforms. No screen coordinates.
  const label = (text: string) => platform === 'ios'
    ? `-ios predicate string:label == ${JSON.stringify(text)} AND accessible == true`
    : `android=new UiSelector().text(${JSON.stringify(text)})`;
  async function visible(text: string, first = false) {
    const selector = label(text);
    if (first) {
      await driver.waitUntil(async () => (await driver.$$(selector)).length > 0, { timeout: 15_000 });
    }
    const element = first ? await driver.$$(selector)[0] : await driver.$(selector);
    await element.waitForDisplayed({ timeout: 15_000 });
    return element;
  }
  try {
    await driver.terminateApp(appId);
    await driver.activateApp(appId);
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
    await driver.saveScreenshot(path.join(artifacts, 'passed.png'));
    await writeFile(path.join(artifacts, 'result.json'), JSON.stringify({ platform, udid, passed: true, scores }, null, 2));
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
