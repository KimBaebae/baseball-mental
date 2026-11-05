# 비용 없는 API 배포 준비

2026-11-05 결정: 월 과금이 발생하는 AWS 서버는 만들지 않는다. 이 구성은 무료 범위의 기능 검증용이다. 스토어 출시용 운영 품질은 별도로 판단한다.

## 준비된 구성

- API: 저장소 루트의 `render.yaml`로 Render Free 웹 서비스를 만들 수 있다. 기존 FastAPI Dockerfile을 그대로 빌드하며 기본 `onrender.com` HTTPS 주소를 사용한다.
- DB: MongoDB Atlas Free(M0) 클러스터. 저장 한도는 문서·인덱스의 비압축 크기 0.5 GB다. `MONGODB_URI`는 Render 비밀 환경 변수로만 입력한다.
- 모바일: Render의 실제 HTTPS 주소를 확인한 뒤 EAS production 환경에 `EXPO_PUBLIC_API_URL`을 등록하고 **새 앱 빌드**를 만든다.

## 비용 0원 조건과 한계

Render에서 Free 서비스만 선택하고 **결제 수단을 등록하지 않는다**. 무료 포함 대역폭·빌드 시간을 넘으면 서비스가 중단될 수 있지만, 결제 수단이 없으면 초과 요금은 청구되지 않는다고 Render가 안내한다. Free 인스턴스는 15분 유휴 후 중지되며 재시작에 약 1분이 걸린다. 따라서 초기 소수 사용자 대상 검증에는 쓰되, 경기 중 즉시 조회나 푸시용 상시 가용성을 약속하지 않는다. 무료 Atlas 역시 용량·성능 제한이 있다.

Render 서비스의 **Connect → Outbound**에서 해당 지역의 송신 IP 범위를 확인하여 Atlas 허용 목록에 추가한다. Render는 무료 서비스를 포함한 지역별 송신 CIDR을 제공하므로 `0.0.0.0/0`로 전체 인터넷을 허용할 필요가 없다. 이 범위는 같은 지역의 다른 Render 서비스와 공유되므로 DB 사용자 암호와 TLS도 유지한다.

따라서 무료 서비스가 실제로 연결되기 전에는 운영 API가 있다고 표시하지 않는다. 공개 출시 전에 데이터 제공 조건, 접근 범위, 복구 가능한 백업, 호출 지연을 다시 검증한다.

## 연결 시 실행 순서

1. 개인 Chrome 프로필에서 Render와 Atlas 무료 계정을 만들고, Render에 결제 수단이 없는지 확인한다.
2. Atlas Free DB 사용자를 만든다. Render 서비스를 만든 뒤 Connect → Outbound에 표시되는 송신 CIDR만 Atlas 허용 목록에 추가한다.
3. 로컬 시즌 DB에서 필요한 컬렉션만 옮기고 원본 중계 HTML·개인 토큰은 제외한다. 전후 문서 수와 경기 상태 수를 비교한다.
4. Render Blueprint를 연결하고 `MONGODB_URI`를 비밀값으로 입력한다. `/health/ready`와 2026년 시즌 조회를 HTTPS에서 검사한다.
5. EAS production API URL을 설정한 뒤 iOS·Android 신규 빌드에서 실제 조회를 확인한다.

참고: [Render Free 안내](https://render.com/docs/free), [Render 비용 FAQ](https://render.com/docs/faq), [Render 송신 IP 범위](https://render.com/docs/outbound-ip-addresses), [Render와 Atlas 연결](https://render.com/docs/connect-to-mongodb-atlas), [Atlas Free 한도](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/).
