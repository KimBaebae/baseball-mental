# 데스크톱 시뮬레이터 테스트

현재 앱은 샘플 데이터와 이전 종이색 테마를 사용한다. 최신 디자인 시안이나 운영 서비스 완성본이 아니다. [배포 준비 현황](release-readiness.md)을 함께 확인한다.

## 빌드 프로필

`apps/mobile/eas.json`의 `desktop-preview`는 `preview`를 상속한다.

- iOS: `ios.simulator=true`, Mac의 iOS 시뮬레이터용 `.app` 아카이브
- Android: 에뮬레이터·실기기에 설치 가능한 APK
- JavaScript 번들을 포함하여 Metro 서버 없이 실행
- iOS 시뮬레이터 빌드는 iPhone 실기기에 설치할 수 없음

저장소 루트에서:

```sh
cd apps/mobile
npx eas-cli@latest build --platform ios --profile desktop-preview
npx eas-cli@latest build --platform android --profile desktop-preview
```

설치에는 macOS의 Xcode·iOS 런타임, Android SDK·Emulator·호스트 아키텍처에 맞는 시스템 이미지가 필요하다. Apple Silicon Mac은 ARM64 Android 이미지를 사용한다.

## iOS

Xcode 27은 Device Hub를 사용한다. Xcode의 Open Developer Tool → Device Hub에서 iPhone 시뮬레이터를 선택한다. 이전 Xcode에서는 Simulator를 사용한다.

```sh
xcrun simctl list devices available
# 선택한 UDID로 실행. 이미 부팅돼 있으면 boot는 생략한다.
xcrun simctl boot <UDID>
open 'devices://device/open?id=<UDID>'
# EAS에서 받은 아카이브를 푼 뒤 실제 .app 경로를 지정한다.
xcrun simctl install <UDID> /path/to/app.app
xcrun simctl launch <UDID> com.kimbaebae.baseballmental
```

## Android

Android Studio Device Manager 또는 SDK의 `avdmanager`로 가상 기기를 만든다. SDK의 `platform-tools`와 `emulator` 디렉터리를 PATH에 추가한다.

```sh
emulator -list-avds
emulator -avd <AVD_NAME>
adb devices
# adb devices에 표시된 에뮬레이터의 실제 serial을 사용한다.
adb -s <SERIAL> install -r /path/to/app.apk
adb -s <SERIAL> shell am start -n com.kimbaebae.baseballmental/.MainActivity
```

## 확인할 흐름

### 브라우저에서 실제 가상 기기 조작

Expo Device Hub를 사용하면 웹 UI 목업이 아니라 실행 중인 iOS·Android 가상 기기의 화면을 스트리밍하고 터치·스크롤할 수 있다. 로컬 SDK 환경 변수를 설정한 터미널에서 실행한다.

```sh
npx expo-device-hub --host 127.0.0.1 --port 3400
```

`http://localhost:3400`에서 기기를 선택한다. Android Emulator의 Qt 창이 열리지 않는 환경에서는 `emulator -avd <AVD_NAME> -no-window`로 가상 기기를 부팅한 뒤 이 화면을 사용한다. Device Hub 서버와 에뮬레이터 프로세스가 실행 중이어야 한다. 기본적으로 localhost에만 노출하며 운영 앱 서버와는 별개다.

### 앱 동작

1. 첫 실행에서 응원팀을 선택한 뒤 최근 종료 경기 월의 메인이 열리고, 앱 재실행 후에도 선택이 유지되는지 확인한다.
2. 메인 상단의 연월 라벨에서 월 모달을 열고 1·2·12월이 없는지 확인한다. 현재 팀 필터를 눌러 다른 팀 모달을 확인한다.
3. 지수와 이벤트 변화가 표시되는지, 초기화 후 다시 재생할 수 있는지 확인한다.
4. 설정에서 응원팀을 변경·저장하고 메인의 팀별 배경·이모지·필터가 바뀌는지 확인한다.
5. 설정 → 가상 경기 체험에서 이벤트를 순서대로 재생하고 공유 버튼으로 각 OS의 공유 UI를 확인한다.
6. 설정 → 알림·푸시 검증에서 로컬 알림 권한과 5초 알림을 확인한다. 앱을 배경으로 보낸 뒤 알림 탭으로 경기 화면에 진입한다.

푸시 토큰 발급과 원격 수신은 별도다. APNs/FCM 자격 증명과 서버 리마인드는 아직 미완료이며 시뮬레이터에서 화면이 열리는 것으로 해당 검증을 대체하지 않는다.

## 출처

- [Expo iOS 시뮬레이터 빌드](https://docs.expo.dev/build-reference/simulators/)
- [Apple Device Hub](https://developer.apple.com/documentation/xcode/device-hub)
- [Android 에뮬레이터 실행](https://developer.android.com/studio/run/emulator-commandline)
- [Expo Device Hub](https://github.com/expo/expo-device-hub)
