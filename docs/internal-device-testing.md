# 스토어 등록 전 실기기 내부 테스트

2026-11-05 기준. 앱 이름 `왜저럴까`, iOS/Android 식별자 `com.kimbaebae.baseballmental`, 운영 API `https://baseball-mental.onrender.com`을 사용한다. 양 플랫폼의 `preview`는 Expo 내부 배포 빌드이며 스토어에 업로드하거나 공개하지 않는다.

| 경로 | 앱 레코드 선행 | 설치 파일 | 이 프로젝트에서의 용도 |
|---|---|---|---|
| Expo 내부 배포 | 불필요 | iOS Ad Hoc IPA, Android APK | 현재 선택. iPhone은 기기 UDID가 포함된 프로비저닝 프로필 필요 |
| TestFlight | App Store Connect 앱 레코드 필요 | App Store용 IPA 업로드 | iOS 스토어 흐름 확인 단계 |
| Play 내부 테스트 | Play Console 앱 레코드 필요 | AAB 업로드 | Google Play 설치·업데이트 흐름 확인 단계 |
| Firebase App Distribution | Firebase 앱 등록 필요 | Android APK 또는 iOS Ad Hoc IPA | 지금은 Expo와 기능이 겹침. iOS UDID 제한은 동일하며 Android AAB 경로는 Play 연결 필요 |

Expo `preview` 빌드는 `apps/mobile/eas.json`에 이미 정의돼 있다. Android APK는 링크를 받은 Galaxy 사용자가 설치할 수 있다. iOS Ad Hoc 빌드는 빌드 시점의 프로필에 포함된 기기에서만 설치할 수 있다. 빌드 링크가 기본 설정에서 공개적으로 접근 가능한지 Expo 프로젝트 설정을 확인하고, 테스트 대상에게만 공유한다.

## 이번 검증 범위

1. iPhone과 Galaxy에서 동일 빌드가 설치·실행되는지 확인한다.
2. 최초 실행에서 응원팀을 선택하고, 앱 재실행 후 선택이 유지되는지 확인한다. 설정 → 응원팀 변경 → 저장 후 메인 배경·이모지·팀 필터가 바뀌는지 확인한다.
3. 운영 API의 최근 종료 경기 월 기본 표시, 시즌 목록·팀별 경기 상세, 연월·팀 모달, 오류·재시도 화면을 확인한다. 1·2·12월이 선택되지 않는지 확인한다.
4. 설정 → 가상 경기 체험에서 스트레스 이벤트·지수 변화·공유 흐름을 확인한다.
5. 백그라운드 복귀 후 화면 상태를 확인한다. 알림은 로컬 알림만 확인한다. 원격 푸시와 경기 전 개인화 리마인드는 서버·APNs/FCM 설정 후 별도로 검증한다.

응원팀 선택은 현재 기기에만 저장한다. 계정 연동·서버 동기화는 아직 없다. 이 테스트가 통과해도 선수별 통계·개인 관전 기록·자동 실시간 이벤트와 스토어 제출 요건까지 완료된 것은 아니다. Play 신규 개인 계정의 정식 공개에는 내부 테스트와 별개로 비공개 테스트 12명·연속 14일 및 production access 신청이 필요하다.

참고: [Expo 내부 배포](https://docs.expo.dev/build/internal-distribution/), [Apple 앱 레코드](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-workflow/), [Play 신규 개인 계정 테스트](https://support.google.com/googleplay/android-developer/answer/14151465), [Firebase iOS 기기 등록](https://firebase.google.com/docs/app-distribution/register-additional-devices), [Firebase Android AAB 배포](https://firebase.google.com/docs/app-distribution/android/distribute-console?apptype=aab).
