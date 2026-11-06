# 내부 테스트 배포 및 버전 관리

설치 링크는 비공개 [baseball-mental-testing](https://github.com/KimBaebae/baseball-mental-testing)에 보관한다. 접근 가능한 테스터만 README와 latest.json을 볼 수 있다. Expo 설치 링크 자체의 접근 정책은 별도다.

## 버전 기준

- 사용자 버전: `apps/mobile/app.json`의 `expo.version`. 기능 릴리스 시 의도적으로 변경한다.
- 빌드 번호: `eas.json`의 `appVersionSource: remote`, preview/production의 `autoIncrement: true`로 EAS가 플랫폼별 증가시킨다. 로컬 버전 숫자를 수동 동기화하지 않는다.
- 코드 커밋만으로 빌드 번호를 증가시키지 않는다. 실제 새 바이너리를 만들 때 증가한다. 실패한 시도 때문에 번호에 빈 구간이 생겨도 정상이다.
- iOS buildNumber와 Android versionCode는 별도이며 같은 숫자일 필요가 없다. 원격 번호를 낮추거나 초기화하지 않는다.

## 빌드와 링크 갱신

1. 소스 main의 Validate monorepo CI 성공 후 비공개 테스트 레포 Actions의 **Build mobile preview**를 실행하고 ios 또는 android를 선택한다. 앱 스토어 제출 없이 실기기용 내부 빌드를 만든다.
2. 워크플로 완료 후 **Sync internal testing links**가 성공한 preview 실기기 빌드를 조회한다. 로컬 CLI 등 다른 경로의 빌드도 매시 13분·43분 예약 조회에 포함된다. GitHub 예약 실행은 지연될 수 있다.
3. 플랫폼별 성공 빌드 중 번호가 현재 기록보다 높은 경우에만 private 레포 README와 latest.json을 커밋한다. 동일 번호의 새 ID, 오래된 번호, 실패·취소·진행 중·스토어·시뮬레이터 빌드는 링크를 변경하지 않는다.
4. 즉시 확인하려면 **Sync internal testing links**를 수동 실행한다. 이 작업은 새 빌드를 만들지 않는다.

동기화는 최근 성공 빌드를 플랫폼별 50개 조회한다. 최초 도입·장기 중단 후에는 EAS 빌드 이력과 비교한다. signed download URL·인증 정보·원본 EAS 응답은 레포나 artifact에 저장하지 않는다.

## CI 권한

비공개 테스트 레포의 Actions secret `EXPO_TOKEN`을 사용한다. 토큰은 Expo의 hyeji.kim 계정으로 범위를 제한한다. GitHub 쓰기에는 해당 레포의 기본 GITHUB_TOKEN만 사용하며, 별도 레포 간 쓰기 토큰이나 deploy key는 사용하지 않는다. PR에서는 실행하지 않는다.

최초 설정: 테스트 레포 Settings → Secrets and variables → Actions에 EXPO_TOKEN을 저장한 뒤 Sync internal testing links를 실행한다. Expo 토큰은 채팅·레포·로그에 기록하지 않는다. 같은 버전으로 두 번 실행해 두 번째 실행에 새 커밋이 없어야 한다. 검증 후 Actions variable `TESTING_SYNC_ENABLED=true`로 예약 실행을 켠다. 인증 미설정 중에는 예약 작업을 건너뛴다.

근거: [Expo 버전 관리](https://docs.expo.dev/build-reference/app-versions/), [GitHub deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys).
