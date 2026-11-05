# Appium UI 테스트

Appium + WebdriverIO + TypeScript로 설치된 iOS·Android 앱을 조작한다. 테스트는 `tests/ui/smoke.test.ts`에서 공통으로 정의하고, 요소 선택과 기기 연결만 플랫폼별로 분기한다. 기본 시나리오는 샘플 경기다. `UI_VERIFY_SEASON=1`을 지정하면 운영 API의 2026 시즌 경기·지수 준비 건수도 확인한다. 원격 푸시는 검증하지 않는다.

## 준비

- Node.js 22.12 이상, npm, macOS/Xcode 및 iOS Simulator
- Android SDK/Emulator, JDK 21. `ANDROID_HOME`, `JAVA_HOME`, SDK `platform-tools`의 PATH 설정
- 가상 기기에 `com.kimbaebae.baseballmental` 설치: [설치 방법](simulator-testing.md)
- 테스트 대상 기기만 선택하도록 `UI_UDID`를 반드시 지정한다. 앱을 재시작하므로 진행 중인 샘플 재생은 초기화된다.

저장소 루트에서 최초 한 번:

```sh
npm ci
npm run ui:setup
```

검증 버전: Appium 3.9.0, WebdriverIO 10.1.0, XCUITest driver 12.22.8, UiAutomator2 driver 8.7.3. 드라이버는 프로젝트의 `.appium/`에 설치하며 Git에 포함하지 않는다. 최신 드라이버는 Appium 4 베타를 요구할 수 있으므로 검증 버전을 지정한다. 이미 설치한 환경에서는 setup을 다시 실행할 필요가 없다.

## 실행

SDK 환경이 설정된 첫 번째 터미널:

```sh
npm run ui:server
```

Appium은 `127.0.0.1:4723`에서만 수신한다. 두 번째 터미널에서 실행 중인 기기 ID를 확인한 뒤 테스트한다.

```sh
xcrun simctl list devices booted
adb devices
UI_PLATFORM=ios UI_UDID=<SIMULATOR_UDID> npm run ui:test
UI_PLATFORM=android UI_UDID=<EMULATOR_SERIAL> npm run ui:test
UI_VERIFY_SEASON=1 UI_PLATFORM=ios UI_UDID=<SIMULATOR_UDID> npm run ui:test
UI_VERIFY_SEASON=1 UI_PLATFORM=android UI_UDID=<EMULATOR_SERIAL> npm run ui:test
npm run ui:typecheck
```

명령의 `<...>`는 실제 ID로 교체한다. 서버 포트를 바꿨다면 테스트에 `APPIUM_PORT`도 지정한다. 최초 iOS 연결은 WebDriverAgent 빌드 때문에 시간이 걸릴 수 있다. 가상 기기 설정이며 실기기 iOS 서명/프로비저닝은 별도다.

## 검증 시나리오

1. 앱을 재시작하고 홈의 첫 번째 `멘탈 기록 열기 →` 버튼을 누른다.
2. `LG vs 두산` 경기 상세와 초기 점수 30을 확인한다.
3. 네 이벤트를 반영하며 점수가 `44 → 67 → 33 → 65`로 변하는지 확인한다.
4. 완료 버튼이 비활성화되어 추가 재생을 막는지 확인한다.
5. `UI_VERIFY_SEASON=1`이면 앱을 다시 열어 운영 서버의 2026 시즌 729경기·지수 준비 703건·자료 확인 중 26건을 확인한다.

고정 좌표나 임의 sleep 없이 화면 요소가 나타날 때까지 기다린다. 문구 변경 시 선택자도 갱신해야 한다. 시나리오의 기대 점수는 앱 구현 함수를 호출해 계산하지 않는다.

## 결과

- 성공: `artifacts/ui/<platform>-<timestamp>/passed.png`, `result.json`
- 실패: 같은 폴더의 `failed.png`, `failed.xml`, `error.txt` (세션 생성 이후)
- 서버/세션 연결 실패: `artifacts/ui/appium.log`와 터미널 오류
- 실행 결과의 종료 코드가 0이면 성공, 그 외는 실패

로그·화면 캡처에는 앱 화면 데이터가 들어갈 수 있어 Git에서 제외한다. 로컬 실행을 우선하며 CI의 네이티브 UI 실행은 아직 연결하지 않았다.

## 공식 문서

- [Appium 설치](https://appium.io/docs/en/latest/quickstart/install/)
- [WebdriverIO Appium 연동](https://webdriver.io/docs/appium/)

## 실행 확인 — 2026-11-02

- iPhone 17 Pro / iOS 26.5 시뮬레이터: 공통 시나리오 통과 (약 21초, 최초 WDA 빌드 제외)
- Baseball_API_36 / Android API 36 에뮬레이터: 공통 시나리오 통과 (약 9초)
- 양쪽 모두 30 → 44 → 67 → 33 → 65 및 완료 버튼 비활성화 확인
- 실패 캡처·화면 XML 저장 확인
- UI 테스트 TypeScript 검사, 모바일 타입 검사·lint·도메인 테스트 통과

이 결과는 샘플 앱의 네이티브 UI 자동화 검증이며 스토어 배포 준비 완료를 의미하지 않는다.
