# 서버 배포 준비 및 검증

현재 서버는 **과거 경기 스냅샷 조회용 기반 구현**이다. 2026-11-05 Render Free와 Atlas Free에 배포하고 2026 시즌 735경기 조회를 실측했다. health와 과거 경기 조회 성공이 실시간 수집·개인 기록·집계·알림 기능 완성을 의미하지는 않는다. [무료 운영 구성](free-deployment-plan.md)을 참고한다.

## 배포 전 확정 항목

1. 호스팅 사업자·프로젝트/계정·리전과 API/DB/로그/백업/네트워크 전체 비용을 확정한다. Cloud Run은 이전 기준안이며 AWS와의 최종 선택은 미확정이다.
2. staging DB를 운영 DB와 분리하고, 인증·TLS·네트워크 접근 범위 및 해당 DB만 접근하는 사용자를 구성한다. 현재 설정 검증은 사용자명/비밀번호 방식 MongoDB URI를 대상으로 한다. 다른 인증 방식을 도입하면 검증 정책을 함께 변경한다.
3. 배포 환경에 `APP_ENV=staging` 또는 `production`을 명시한다. MongoDB URI는 secret manager에서 주입한다. 모바일의 `EXPO_PUBLIC_` 변수로 전달하지 않는다.
4. 현재 API는 애플리케이션 사용자 인증이 없으므로 staging을 플랫폼 IAM/접근 제한으로 보호한다. 공개 운영 API로 전환하기 전에 데이터 제공 범위와 사용자 인증·인가를 확정한다.
5. commit SHA와 이미지 digest를 기록하고 같은 digest를 staging에서 검증한 뒤 운영에 승격한다. `latest` 태그만으로 배포 버전을 결정하지 않는다.

## 환경 변수

| 변수 | 설정 |
|---|---|
| `APP_ENV` | `local` / `staging` / `production`; 컨테이너 배포 시 명시 필수 |
| `MONGODB_URI` | 인증된 `mongodb+srv://...` 또는 `mongodb://...?tls=true`; 비밀값 |
| `MONGODB_DATABASE` | 환경별 DB 이름 |
| `ENABLE_KBO_PROBE` | staging/production에서는 `false` |
| `PORT` | 컨테이너 수신 포트, 기본 8080 |

non-local 환경은 DB URI 없음·인증 누락·TLS 해제·서버 인증서 검증 해제·과거 검증 수집기 활성화를 거부한다. 이는 DB 설정 검사이며 데이터 재이용 권한이나 네트워크 보안 전체를 검증하지 않는다. 로컬 `.env.example`과 Compose는 기존 로컬 개발용 기본값을 유지한다.

## 사전 검사

`apps/server`에서 secret manager나 로컬 비밀 환경 파일로 위 변수를 주입한 뒤 실행한다. 명령 기록에 URI 자체를 넣지 않는다.

```sh
uv run python -m app.deployment preflight
uv run python -m app.deployment preflight --check-db
```

첫 명령은 배포 설정만 검사한다. `--check-db`는 MongoDB에 ping하되 인덱스 생성·데이터 쓰기는 하지 않는다. 실제 앱 시작 시 Beanie가 인덱스를 초기화하므로 인덱스 생성 권한과 운영 변경 영향을 별도 확인해야 한다. 체크 실패 시 비밀 URI나 응답 본문을 출력하지 않고 실패 유형과 종료 코드 1을 반환한다.

## 배포 후 검사

```sh
uv run python -m app.deployment smoke https://SERVICE_HOST --game-date 2026-09-01
```

- `/health/live`, `/health/ready`가 모두 200과 `{"status":"ok"}`를 반환해야 한다.
- `/v1/games`가 리스트를 반환하고, 반환된 각 항목은 현재 스냅샷 계약을 만족해야 한다.
- empty list는 인프라 검사상 성공이지만 데이터 확보 성공을 의미하지 않는다.
- redirect는 따라가지 않는다. localhost 외에는 HTTPS를 요구한다.
- IAM 서비스라면 audience가 서비스 URL인 identity token을 `SMOKE_ID_TOKEN` 환경 변수로 주입한다. 토큰을 인자로 쓰거나 로그에 출력하지 않는다. 토큰 생성은 호스팅 환경에 맞춰 구성한다.

현재 스모크는 읽기만 수행한다. 개인 기록 API가 구현되면 테스트 계정의 기록 생성/재조회/삭제와 권한 분리 검증을 별도로 추가한다.

## 컨테이너와 운영 절차

기존 `apps/server/Dockerfile`은 non-root 사용자로 실행하며 서버 코드만 이미지에 복사한다. 이 검사 모듈도 `app/` 안에 있으므로 같은 이미지에서 실행 가능하다. 로컬 환경 파일과 자격 증명은 빌드 컨텍스트에서 제외한다.

- readiness: MongoDB ping을 포함하는 `/health/ready`를 서비스 준비 검사에 사용한다.
- liveness: `/health/live`를 프로세스 검사에 사용한다. DB 장애를 무조건 프로세스 재시작으로 처리하지 않는다.
- 스케줄러: 현재 수집기는 과거 검증용이며 자동 스케줄링하지 않는다. 운영 수집기는 데이터 정규화·재시도·정정·중복 방지 검증 후 별도 구현한다.
- 로그: 요청 실패율·DB 장애·수집 누락을 관측한다. DB URI/토큰/원본 중계 본문은 로그에 남기지 않는다.
- 백업: 운영 DB 제공자의 백업·복원 정책을 확정하고 별도 DB에 실제 복원한 증거를 남긴다.
- 복구: 실패한 배포를 이전 정상 이미지 digest로 되돌린 뒤 같은 스모크를 실행한다. DB 변경이 하위 호환되는지 확인한다. 백업 복원은 이미지 롤백과 별개다.

## 현재 완료와 남은 작업

완료: 컨테이너 기반, liveness/readiness, 배포 설정 검사, 읽기 전용 DB 사전 검사, HTTP 스모크 및 실패 동작 테스트.

미완료: 운영 자동 수집, 인증·개인 기록·통계·푸시, 실제 데이터 정정/복구, 백업 복원, 무료 서비스의 유휴 복귀 지연 검증. 월 과금 AWS 리소스는 생성하지 않았다.
