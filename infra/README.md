# 실행 및 배포 구성

- `compose.yaml`: 로컬 API + MongoDB. 공개 포트는 localhost에만 바인딩한다.
- `apps/server/Dockerfile`: 서버 단독 이미지. 빌드 컨텍스트는 `apps/server`다.
- 모바일 EAS 설정은 `apps/mobile/eas.json`이다. EAS 명령은 `apps/mobile`에서 실행한다.

```sh
docker compose -f infra/compose.yaml up --build
```

2026-11-05 기준 Render Free API와 Atlas Free DB를 수동 배포했다. [무료 운영 구성](../docs/free-deployment-plan.md)에 주소와 검증 범위를 기록했다. GitHub Actions는 검증과 서버 이미지 빌드만 수행하며 Render 자동 배포는 아직 연결하지 않았다. 모바일과 서버는 같은 저장소에서 독립적으로 배포한다.

배포 설정 사전 검사와 배포 후 HTTP 스모크는 [서버 배포 절차](../docs/server-deployment.md)에 정리되어 있다. staging/production의 `APP_ENV`를 명시하고 검증용 서비스를 공개하기 전에 플랫폼 접근 제한을 적용한다.
