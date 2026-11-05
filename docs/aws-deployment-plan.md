# AWS 운영 API 배포안

상태: AWS 개인 계정 로그인 및 기존 리소스 확인 대기. 이 문서만으로 리소스는 생성되지 않는다.

## 첫 운영 구성

- API: 서울 리전의 단일 Lightsail 인스턴스. 현재 FastAPI 컨테이너를 배포하고, HTTPS 프록시를 앞에 둔다. 인스턴스 고정 IP만 MongoDB 접속 허용 목록에 등록한다.
- DB: 별도 MongoDB Atlas Free 클러스터(MongoDB 8.0, 저장 한도 0.5 GB). API와 DB는 서로 다른 자격 증명을 사용하며, URI는 서버에서만 비밀값으로 주입한다. 현재 로컬 DB 디렉터리 크기는 약 21 MB이나 Atlas 용량은 문서·인덱스의 비압축 크기 기준이므로 이전 후 실제 사용량을 확인한다.
- 모바일: 운영 HTTPS URL을 EAS production 환경의 `EXPO_PUBLIC_API_URL`로 설정하고 새 빌드를 만든다. DB URI는 모바일 환경에 넣지 않는다.
- 데이터 이전: 로컬 `season_games` 등 필요한 컬렉션의 문서 수와 검증 상태를 먼저 기록하고, 원본 중계 HTML·개인 토큰을 제외한 뒤 운영 DB로 옮긴다. 이전 전후 경기 수·멘탈 리포트 수와 표본 API 응답을 비교한다.

## 비용과 운영상 제약

Lightsail Linux 공개 IPv4 포함 1 GB 플랜은 월 USD 7, 2 GB 플랜은 월 USD 12이다(초과 사용·세금 별도). 1 GB에서 API와 HTTPS 프록시를 먼저 측정하고 메모리가 부족하면 2 GB로 올린다. Atlas Free 클러스터는 기본 사용료가 없지만 0.5 GB 저장 한도와 무료 티어의 성능·운영 제약이 있다. 백업 기능의 제공 여부와 요금은 계정에서 확인하고, 운영 시작 전 복원 가능한 별도 백업을 마련한다.

## 실행 전 확인

1. 개인 AWS 계정 인증을 갱신하고 기존 인스턴스·도메인·과금 상태를 읽기 전용으로 확인한다.
2. HTTPS에 사용할 도메인, Atlas 계정·클러스터, 고정 IP를 확정한다. 비용이 발생하는 리소스 생성 전 월 비용을 다시 확인한다.
3. Atlas의 IP 허용 목록은 API 고정 IP로 한정하고 DB 사용자에 필요한 권한만 부여한다.
4. `APP_ENV=production`, 인증·TLS가 적용된 `MONGODB_URI`, 전용 `MONGODB_DATABASE`를 주입하고 `python -m app.deployment preflight --check-db`를 실행한다.
5. 배포한 이미지의 commit SHA와 digest를 기록하고 HTTPS health 및 실제 경기 조회를 검사한다.
6. EAS production API URL을 설정한 새 iOS·Android 빌드에서 같은 경기를 조회한다.

가격 참고: [AWS Lightsail 가격](https://aws.amazon.com/lightsail/pricing/), [Atlas 무료 클러스터 한도](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/).
