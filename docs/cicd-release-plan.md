> 아래는 최초 점검 기록이다. 이후 반영 상태는 [실행 순서](execution-order.md)와 [배포 자동화](release-automation.md)를 확인한다. 신규 Play 개인 계정 생성은 소유자가 확인했으며, 콘솔 인증 완료 여부는 미확인이다.

# CI/CD 점검 및 플랫폼별 출시 작업 명세

2026-11-02 확인. **검증 CI는 운영 중이며, 운영 서버 배포와 스토어 제출 CD는 미구축이다.** 현재 앱은 샘플 경기 기반 기술 검증 버전이다. 아래의 미완료 항목은 출시 완료로 간주하지 않는다.

## 1. 확인 범위와 현재 설정

저장소 설정, GitHub Actions 실행 결과·repository secrets 이름 목록·environments·rulesets·main 보호 여부, EAS 빌드 목록을 직접 조회했다. App Store Connect, Play Console, 클라우드 프로젝트의 실제 리소스 및 EAS 서명/푸시 자격 증명은 이번 점검에서 조회하지 않았다. 저장소에 없는 외부 설정을 존재하지 않는다고 단정하지 않는다.

| 영역 | 확인 결과 | 의미 / 누락 |
|---|---|---|
| GitHub Actions | `.github/workflows/check.yml`, 모든 push/PR에서 실행 | 모바일·서버 변경과 무관하게 두 job 모두 실행 |
| 모바일 CI | Node 22, npm ci, typecheck, lint, 도메인 테스트, Expo all-platform export | JS 번들 검증. 서명된 네이티브 빌드·실기기 테스트는 아님 |
| 서버 CI | Ubuntu 22.04, uv lock, Ruff, pytest + MongoDB 8 통합 테스트, OpenAPI·requirements 동기화, Docker build | 이미지를 registry에 push하거나 서버에 배포하지 않음 |
| 최근 CI | `79f864b`의 모바일·서버 job 성공 | [실행 결과](https://github.com/KimBaebae/baseball-mental/actions/runs/41396861852) |
| Appium | iOS 26.5·Android API 36 로컬 샘플 흐름 통과 | `ui:typecheck`와 `ui:test` 모두 현재 CI에 없음. [실행 명세](ui-testing.md) |
| GitHub 배포 설정 | repository secrets 0개, environments 0개, rulesets 0개, main protected=false | EAS/클라우드 배포 인증·승인 환경·필수 체크 미설정. EAS 측 비밀값 유무와는 별개 |
| EAS build | development / simulator / preview / desktop-preview | `production`, `submit` 설정 없음 |
| EAS 최근 빌드 | iOS desktop-preview, Android desktop-preview 및 preview 모두 FINISHED | 모두 INTERNAL. iOS는 시뮬레이터 앱, Android는 APK |
| 버전·식별자 | `왜저럴까 POC`, version 1.0.0, `com.baseballmentalpoc.app`, scheme `baseball-mental-poc` | 출시 명칭·식별자 확정, buildNumber/versionCode 증가 규칙 필요 |
| 서버 운영 | 로컬 Compose + Dockerfile, 운영 배포 workflow/IaC 없음 | 기존 문서상 Cloud Run 기준안. 실제 프로젝트·리전·DB·비용 미확정 |
| OTA | EAS Update 채널·runtimeVersion 및 배포 workflow 없음 | 첫 출시 필수 아님. 도입 시 호환성·되돌리기 별도 설계 |

EAS 확인 빌드: iOS `c0a59436-5ecf-4570-9923-2b20bfa964ae`, Android `ef3dccd6-24a0-492f-b4a9-d537ce046446`. 빌드 목록 성공은 스토어 업로드/심사 성공을 뜻하지 않는다.

## 2. 양 플랫폼 공통 출시 차단 작업

P0는 정식 출시 전에 충족해야 한다. 운영 개인 데이터 처리 방식이 정해지면 관련 API와 스토어 신고를 함께 확정한다.

| ID | 우선순위 | 작업 | 완료 기준 | 선행 |
|---|---|---|---|---|
| C01 | P0 | 경기 데이터 수집·사용 조건 확정 | 자동 수집/서비스 제공 범위 확인, 실패·제한 시 대응 정의 | 없음 |
| C02 | P0 | 이벤트 정규화·정정·복구 | 선수 귀속, 사건 전후 아웃·주자·점수 대조; 중복·정정·중단 복구 검증; 수집 지연 표시 | C01 |
| C03 | P0 | 사용자 식별·기록 계약 | 개인 기록 접근 범위, 저장·삭제·기기 변경 정책 확정; 인증·인가 테스트 | 없음 |
| C04 | P0 | 실제 서버 기능 | 자동 수집 작업, 개인 경기 기록, 시즌/선수 통계, 응원팀 설정, 푸시 구독 API 구현 | C02,C03 |
| C05 | P0 | 운영 API·DB 구축 | 호스팅/DB 비용·리전 확정, HTTPS, 비밀값 분리, readiness DB 검사, 로그·오류 알림·백업 및 복원 검증 | C03 |
| C06 | P0 | 앱 실제 API 연결 | 샘플 흐름 교체, 재실행 후 기록 유지, 로딩·오류·재시도·지연·경기 없음 처리 | C04,C05 |
| C07 | P0 | 확정 디자인 반영 | 다크 테마·Bagel 타이포·팀 색·검증된 구장/응원석 이미지와 대체 이미지 적용; 자산 사용권 확인 | 디자인 명세 |
| C08 | P0 | 경기 전 개인화 알림 | 경기 일정 기반 예약, 동의/거부 처리, 중복 발송 방지, 취소·일정 변경 반영, 실패 토큰 처리 | C04,C05 |
| C09 | P0 | 제품 품질 검증 | 실제 흐름 Appium 검증 + 양 플랫폼 실기기 검증; 공유·오프라인·백그라운드 복귀·글자 확대 확인 | C06~C08 |
| C10 | P0 | 출시 정보·개인정보 | 실제 동작과 일치하는 설명/스크린샷, 지원 URL, 개인정보처리방침, 데이터 수집 목록 및 보관/삭제 정책 | C03,C06 |

구체적인 데이터 검증 기준은 [서버 계획](backend-plan.md)을 따른다. 실시간 경기가 없는 기간에는 과거 경기 재생으로 로직을 검증하고, 실제 운영 수집 지연 검증은 별도 증거로 남긴다. 알 수 없는 호수비를 임의로 자동 판정하지 않는다.

## 3. iOS 출시 작업

| ID | 우선순위 | 작업 | 완료 기준 |
|---|---|---|---|
| I01 | P0 | Developer / App Store Connect 확인 | 유효한 팀·권한·약관, 출시 bundle ID 등록, 앱 레코드 생성 |
| I02 | P0 | production EAS 프로필 | 시뮬레이터가 아닌 App Store 배포용 서명 IPA 생성; 인증서·프로비저닝 확인; buildNumber 증가 규칙 적용 |
| I03 | P0 | iOS 푸시 자격 증명 | APNs 및 앱 entitlement 확인, 실제 iPhone에서 권한 수락/거부·배경 수신·알림 탭 진입 확인 |
| I04 | P0 | TestFlight 검증 | production 계열 빌드 업로드, iPhone 설치, 운영/검증 API 연결·기록·알림 검증; 외부 테스트 시 해당 심사 고려 |
| I05 | P0 | 스토어 메타데이터 | 실제 앱명/아이콘/스크린샷, App Privacy, 연령 등급, 수출 규정 답변, 지원·개인정보 URL, 심사 노트/필요 시 테스트 계정 |
| I06 | P0 | 제출·출시 | 당시 SDK 제출 요건 확인, 심사 제출, 지적 수정, 승인 후 공개 방식 선택 |
| I07 | P1 | 제출 자동화 | EAS Submit용 App Store Connect 인증 연결 및 앱 ID 설정, 선택한 빌드만 TestFlight 업로드 |

현재 시뮬레이터 `.app`은 TestFlight/App Store 제출물이 아니다. `supportsTablet=false`인 현 범위를 유지하더라도 지원 기기·화면 요구사항은 제출 시 확인한다. 계정 생성 기능을 제공하면 앱 내 계정 삭제 요구사항도 함께 검토한다. EAS Submit 업로드 후에도 스토어 정보 작성과 심사 제출 단계가 남는다.

## 4. Android 출시 작업

| ID | 우선순위 | 작업 | 완료 기준 |
|---|---|---|---|
| A01 | P0 · 먼저 확인 | Play Console 등록 상태·계정 유형·생성일·인증 | 실제 콘솔에서 출시 가능한 상태 확인, 적용 테스트 요건 확정 |
| A02 | P0 | package / 서명 확정 | 최종 package 확정, 기존 EAS keystore 사용 가능 여부와 백업 확인, Play App Signing 설정 |
| A03 | P0 | production AAB | APK 대신 서명된 AAB 생성, versionCode 증가 규칙, 제출 시 target API·네이티브 라이브러리 요건 충족 확인 |
| A04 | P0 | Android 푸시 | FCM v1 인증과 앱 Firebase 설정 연결, 알림 권한/채널, 실제 Galaxy 배경 수신·탭 진입 확인 |
| A05 | P0 | 최초 업로드·테스트 | 최초 Play 업로드 수동 진행, internal 설치 및 사전 출시 보고서 확인; 해당 계정은 closed test와 production access 신청 |
| A06 | P0 | 스토어 등록정보 | 실제 스크린샷·아이콘·그래픽, Data safety, 개인정보 URL, 콘텐츠 등급·광고 여부·앱 액세스 답변 |
| A07 | P0 | 심사·출시 | production access 충족 후 릴리스 심사, 공개 범위/출시 방식 확정 |
| A08 | P1 | 제출 자동화 | Google 서비스 계정의 최소 Play 권한, EAS Submit 인증, 제출 track 명시 및 빌드 ID 고정 |

**일정 분기:** 2023-11-13 이후 생성된 개인 개발자 계정은 최소 12명이 연속 14일 참여한 비공개 테스트 후 production access를 신청해야 한다. 이 프로젝트에 적용되는지는 계정 확인 전까지 미확정이다. 적용되면 일주일 내 정식 공개 목표와 양립하지 않는다. internal 테스트 또는 APK 공유만으로 이 조건을 충족하지 않는다. 14일 후에도 접근 승인·앱 심사가 별도로 남는다. [Google 공식 요건](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en-GB)

## 5. CI/CD 구성 작업 명세

첫 출시를 수동 제출로 진행할 수 있으므로 전체 CD 자동화가 필수 선행은 아니다. 다만 검증된 버전과 실제 배포 버전을 추적하고 실패 시 되돌릴 절차는 필요하다.

| ID | 단계 | 추가 작업 | 완료 기준 |
|---|---|---|---|
| D01 | PR 검증 | 기존 CI에 `ui:typecheck`, main 필수 체크 적용 | 실패한 변경의 병합 차단; 직접 push 예외 정책 명시 |
| D02 | 네이티브 QA | 수동 실행/출시 후보용 Appium job, iOS macOS·Android emulator runner, 테스트 빌드 다운로드 | 양 플랫폼 성공, 실패 캡처·로그 artifact 보관, 빌드 commit 일치 확인 |
| D03 | 서버 staging CD | 이미지 registry, commit SHA 태그, 클라우드 인증(OIDC 우선), 배포·readiness·스모크 검사 | 같은 이미지로 재배포 가능, 실패 시 이전 이미지 복귀 |
| D04 | 서버 production CD | 환경 분리, 필요한 secrets, 배포 승인, DB 변경 호환성·백업 절차 | 이전 앱 버전과 호환, 운영 확인과 복구 절차 기록 |
| D05 | 모바일 배포 후보 | EAS production/submit 프로필, EXPO_TOKEN 등 인증, 명시적 tag/수동 실행 | CI 통과 SHA에서 서명 빌드, TestFlight/Play 테스트 track 업로드, 결과 링크 기록 |
| D06 | 정식 공개 | 스토어 심사 상태·수동 공개 또는 단계적 출시 절차 | 승인된 버전만 공개, 장애 시 출시 중단·서버 호환 유지 |
| D07 | 선택 | OTA 채널/runtimeVersion·업데이트·되돌리기 | JS 호환 범위 검증. 네이티브 변경은 새 스토어 빌드 |

제안 흐름: PR 검사 → 병합 → staging API 배포 → 후보 네이티브 빌드 → Appium·실기기 확인 → 운영 서버 배포 → TestFlight/Play 테스트 → 심사 → 정식 공개. 모바일·서버는 독립 배포하며 API 하위 호환을 유지한다. 모든 push마다 유료 EAS 빌드를 자동 실행하는 구성은 비용·쿼터 확인 후 결정한다.

## 6. 권장 실행 순서

1. A01과 I01: 스토어 계정·권한 확인을 즉시 진행하여 외부 대기 시간을 파악한다.
2. C01~C03: 데이터 사용·정규화와 개인 기록 계약을 확정한다.
3. C04~C08 및 D03: 서버 staging과 실제 앱 기능·디자인·푸시를 연결한다.
4. I02~I04 / A02~A05 및 D02: 서명 빌드를 만들어 플랫폼별 테스트에 진입한다. 준비된 Android 후보는 필요한 비공개 테스트를 시작한다.
5. C09~C10 / I05~I06 / A06~A07: 실제 검증 결과와 스토어 자산을 갖춰 심사·공개한다.

작업 담당 범위: 구현·설정·자동 테스트·문서화는 저장소에서 진행 가능하다. 계정 본인 인증/약관, 접근 권한 부여, 테스터 확보와 실기기 협조는 계정 소유자 참여가 필요하다. Google production access와 각 스토어 심사는 외부 처리다. 이 문서는 계획이며 배포 인증이나 유료 리소스를 생성하지 않았다.

## 공식 참고 자료

- [Expo Google Play 제출 및 최초 수동 업로드](https://docs.expo.dev/submit/android/)
- [Expo 스토어 제출](https://docs.expo.dev/deploy/submit-to-app-stores/)
- [Apple App Review](https://developer.apple.com/app-store/review/)
- [Apple 스크린샷 규격](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications)
