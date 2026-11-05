# 모바일 릴리스 후보 자동화

## 구현된 범위

`.github/workflows/mobile-release.yml`의 **Build mobile release candidate**는 수동 실행으로 플랫폼 하나의 스토어용 바이너리를 만든다. 모든 push마다 EAS 빌드를 실행하지 않는다. 스토어 업로드·심사 제출·공개는 실행하지 않는다.

1. main에서만 실행한다.
2. 동일한 commit SHA의 최신 `Validate monorepo` push 실행이 완료·성공하고, mobile/server job이 모두 성공했는지 확인한다. CI 진행 중이거나 누락·실패·skip이면 중단한다.
3. `mobile-release` GitHub Environment의 `EXPO_TOKEN`을 확인한다.
4. 고정된 EAS CLI **27.2.0**으로 production 빌드를 요청하고 완료를 기다린다.
5. 결과의 commit SHA·플랫폼·STORE 배포·production 프로필·FINISHED를 확인한다.
6. 빌드 ID·버전·commit SHA만 30일 artifact로 보관한다. 임시 서명 URL이 포함된 EAS 원본 JSON은 업로드하지 않는다.

## 최초 실행 전 필요한 외부 설정

- GitHub `mobile-release` Environment는 생성했고 배포 가능 브랜치를 `main`으로 제한했다. 승인자는 설정하지 않았다.
- 해당 Expo 프로젝트 권한이 있는 `EXPO_TOKEN`을 Environment secret으로 등록한다. 값을 저장소에 넣지 않는다.
- EAS production 환경에 공개 가능한 HTTPS `EXPO_PUBLIC_API_URL`을 설정한다. API URL은 앱에 포함되는 값이므로 비밀이 아니다. 서버의 DB URI·푸시 서버 키는 앱 환경에 넣지 않는다.
- 최종 표시 이름 `왜저럴까`와 양 플랫폼 식별자 `com.kimbaebae.baseballmental`를 앱 설정에 반영했다. 새 식별자의 스토어 등록·서명은 별도로 확인한다.
- EAS에서 iOS App Store 배포 인증서·프로비저닝과 Android keystore를 준비한다. 첫 production 설정은 대화형 CLI로 확인한다. 자동 workflow는 자격 증명을 물어보지 않고 실패한다.
- `eas.json`의 `appVersionSource`는 remote로 변경했다. production의 `autoIncrement=true`로 빌드 번호 중복을 방지한다. 최초 실행 전 `eas build:version:set`으로 플랫폼별 원격 버전을 스토어의 기존 최대 버전과 맞춘다. 앱의 사용자 표시 version은 별도로 변경한다.
- EAS 빌드 할당량/비용을 확인한다. 이 workflow를 실행하면 원격 빌드가 실제 발생한다.

`apps/mobile`에서 계정 설정을 확인할 때는 `npx eas-cli@27.2.0`을 사용한다. 일반 EAS 명령 예시는 [Expo 공식 문서](https://docs.expo.dev/build/building-on-ci/)를 따른다.

## 실행과 결과

GitHub Actions → Build mobile release candidate → Run workflow → main → ios 또는 android.

`production` 프로필은 iOS 시뮬레이터 `.app`이 아닌 스토어용 서명 빌드, Android는 AAB를 생성한다. 개발/preview 프로필은 유지된다. 결과 artifact의 `build.json`에서 빌드 ID를 확인하고 Expo 프로젝트 빌드 화면에서 다운로드한다. workflow가 실패/시간 초과/취소되어도 이미 시작한 EAS 원격 빌드가 중단된다고 가정하지 않는다. Expo에서 해당 빌드 상태를 확인한 후 재실행한다.

현재 프로필은 **스토어 제출 가능한 형식의 빌드 구성**이며 서비스 기능·데이터·정책 준비 완료를 의미하지 않는다. 운영 API와 DB 연결 및 preview 빌드의 양 플랫폼 Appium 조회는 확인했다. 실제 스토어 자격 증명과 EAS production 빌드는 아직 이 workflow에서 검증하지 않았다.

2026-11-05 계정 점검: `mobile-release` Environment의 `main` 브랜치 제한을 GitHub API에서 다시 읽어 확인했다. Expo 토큰은 개인 계정 `hyeji.kim`의 Developer 권한으로 제한해 만들고 `EXPO_TOKEN` Environment secret으로 저장했으며, GitHub API에서 이름과 갱신 시각을 확인했다. EAS production 환경의 API 주소와 원격 iOS/Android 빌드 번호 1도 확인했다. 이 workflow의 실제 빌드 실행 결과는 별도로 기록한다.

## 아직 남은 단계

- 자동 이벤트·개인 기록·통계 등 제품 기능 완성, production 서명 자격 증명 확인
- 네이티브 Appium CI 연결 및 실제 API 흐름 테스트 (현재 로컬 smoke만 검증됨)
- TestFlight/Play 업로드: 계정·앱 레코드·API 인증을 준비한 뒤 **선택한 빌드 ID**로 제출
- Android 최초 수동 Play 업로드, 신규 개인 계정에 적용되는 비공개 테스트/production access
- 스토어 메타데이터·실제 화면 스크린샷·심사·공개

fastlane 도입과 match로의 서명 이전은 확정하지 않았다. 현재 구성은 EAS를 빌드·서명 담당으로 유지하며 제출 도구는 별도 결정할 수 있다. EAS와 match가 인증서를 독립적으로 생성·갱신하도록 중복 구성하지 않는다.

## 검증

- `node --test scripts/release/*.test.mjs`: 다른 SHA, pending/failed CI, skipped job, 다른 플랫폼/내부 빌드 거부 및 메타데이터 비밀값 제외 검증
- 기존 CI에 `npm run ui:typecheck`와 위 릴리스 스크립트 테스트 추가
- 실제 빌드/스토어 업로드/인증서 생성은 자동화 코드 검증과 별도

참고: [원격 버전 관리](https://docs.expo.dev/build-reference/app-versions/), [EAS 환경 변수](https://docs.expo.dev/eas/environment-variables/).

## 서버 이미지 publication

`Publish server image` workflow는 main의 동일 commit에 대한 최신 검증 CI 성공을 확인한 후 서버 이미지를 GHCR에 push한다. 결과는 commit SHA 태그와 digest artifact로 기록한다. 런타임·DB·클라우드 리소스를 생성하거나 서버 URL을 공개하지 않는다. 최초 실행 전 패키지 저장/전송 비용과 접근 범위를 확인하며, 실제 호스팅으로 배포할 때는 기록된 digest를 사용한다.
