# 실행 및 배포 구성

- `compose.yaml`: 로컬 API + MongoDB. 공개 포트는 localhost에만 바인딩한다.
- `apps/server/Dockerfile`: 서버 단독 이미지. 빌드 컨텍스트는 `apps/server`다.
- 모바일 EAS 설정은 `apps/mobile/eas.json`이다. EAS 명령은 `apps/mobile`에서 실행한다.

```sh
docker compose -f infra/compose.yaml up --build
```

운영 리소스는 아직 생성하지 않았다. Cloud Run 기준안이며 배포 프로젝트, 리전, MongoDB 접근 방식과 비용을 확정해야 한다. GitHub Actions는 현재 검증과 서버 이미지 빌드만 수행하며 자동 운영 배포는 하지 않는다. 향후 모바일과 서버는 같은 저장소에서 독립적으로 배포한다.

배포 설정 사전 검사와 배포 후 HTTP 스모크는 [서버 배포 절차](../docs/server-deployment.md)에 정리되어 있다. staging/production의 `APP_ENV`를 명시하고 검증용 서비스를 공개하기 전에 플랫폼 접근 제한을 적용한다.
