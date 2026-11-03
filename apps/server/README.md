# 왜저럴까 서버

Python 3.13 · FastAPI · Beanie · MongoDB 기반 API와 수집 작업이다. 서버 기반, 과거 경기 검증용 저장·조회와 2026 시즌 팀별 멘탈지수 계산·조회 경로를 구현했다. 운영 배포, 실시간 이벤트 정규화, 인증, 개인 기록·시즌 집계·푸시는 아직 구현하지 않았다.

## 실행

[uv](https://docs.astral.sh/uv/getting-started/installation/) 설치 후 이 디렉터리에서 실행한다.

```sh
uv sync --locked
cp .env.example .env
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

MongoDB가 필요하다. Docker가 있다면 저장소 루트에서 다음 명령으로 로컬 API와 DB를 함께 실행할 수 있다.

```sh
docker compose -f infra/compose.yaml up --build
```

API 문서는 `http://127.0.0.1:8000/docs`에서 확인한다. Compose는 로컬 개발용이며 외부 공개·운영용 구성이 아니다. 데이터 볼륨은 컨테이너 재시작 후에도 유지된다. 운영 DB는 별도 관리형 MongoDB와 제한된 네트워크 접근을 구성해야 한다.

## API

| 경로 | 동작 |
|---|---|
| `GET /health/live` | 프로세스 생존 확인 |
| `GET /health/ready` | 실제 MongoDB 연결 확인, 미설정·장애 시 503 |
| `GET /v1/games?game_date=2026-09-01` | DB에 저장된 날짜별 경기 스냅샷 조회 |
| `GET /v1/games/{game_id}` | 저장 경기 조회, 없으면 404 |
| `GET /v1/seasons/2026/games` | 팀·날짜 필터와 시즌 수집 범위 |
| `GET /v1/games/{game_id}/mental?team_id=LG` | 관전 여부와 무관한 팀별 멘탈지수 |

DB 미설정 상태에서는 조회 요청에 503을 반환한다. 샘플 데이터를 자동 삽입하지 않는다. 현재 API는 개인 정보 없는 검증용 읽기 API이며, 배포 전 데이터 이용 범위와 접근 정책을 확정해야 한다. 임의 쓰기·수집 요청을 외부 HTTP API로 노출하지 않는다.

응답의 `verification=historical-response-only`는 과거 응답 조회만 검증했다는 뜻이다. `collected_at`은 수집 요청 시작 시각이며 원본 이벤트 발생 시각이 아니다. 주자·아웃·선수 정보나 실시간성을 보장하지 않는다.

## 수집 작업

DB 저장 없이 공개 응답 형식만 확인:

```sh
uv run python -m workers.probe_kbo 20260901LGOB0
```

명시적으로 허용한 과거 경기 한 건을 DB에 저장:

```sh
ENABLE_KBO_PROBE=true uv run python -m workers.collect 20260901LGOB0
```

경기당 문자중계·스코어 두 요청만 실행한다. 자동 스케줄링은 없다. 정규화된 텍스트·득점의 해시로 동일 응답의 재시도를 중복 저장하지 않고, 다른 해시는 별도 버전으로 보존한다. 늦게 끝난 이전 수집 작업이 최신 스냅샷을 덮어쓰지 않도록 수집 시각으로 비교한다. 텍스트 원문 자체는 DB와 Git에 저장하지 않는다. 이 버전 기록은 향후 선수·이벤트별 정정 처리의 완성본이 아니다.

## 검증과 API 계약

```sh
uv run ruff check .
uv run pytest
TEST_MONGODB_URI=mongodb://localhost:27017 uv run pytest -m integration
uv run python export_openapi.py
uv export --no-dev --no-emit-project --no-header --format requirements-txt --output-file requirements.txt
```

MongoDB가 없으면 통합 테스트는 건너뛴다. CI에서는 MongoDB 서비스를 실행하여 중복 저장·정정·늦은 응답·새 API 연결에서의 영속 조회를 검증한다. 통합 테스트는 `test_baseball_`로 시작하는 임시 DB를 만들고 종료 시 해당 DB만 삭제한다.

OpenAPI는 [contracts/openapi.json](../../contracts/openapi.json)에 생성한다. CI는 스키마와 Docker 의존성 파일이 소스·잠금 파일과 일치하는지 검사한다. 앱은 실행 시 응답을 검증하는 TypeScript 클라이언트로 연결한다. 자동 클라이언트 생성은 적용하지 않았다.

## 배포 사전 검사

staging/production은 `APP_ENV`를 명시하고 인증·TLS MongoDB를 설정해야 한다. 과거 검증 수집기는 non-local에서 활성화할 수 없다.

```sh
uv run python -m app.deployment preflight
uv run python -m app.deployment preflight --check-db
uv run python -m app.deployment smoke https://SERVICE_HOST --game-date 2026-09-01
```

환경 변수, 접근 제한, 배포 후 검사와 복구 절차는 [서버 배포 문서](../../docs/server-deployment.md)를 따른다. 인프라 검사가 성공해도 운영 데이터·서비스 기능의 완료를 의미하지 않는다.

2026 시즌 수집·재개 방법과 계산 기준은 [지난 경기 멘탈지수](../../docs/season-mental.md)를 따른다.
