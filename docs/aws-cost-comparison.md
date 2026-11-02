# AWS 비용 비교와 호스팅 선택

2026-11-02 기준. 금액은 USD·세전 계획치이며 실제 청구서가 아니다. 기존 소규모 도서 서비스의 인프라 템플릿과 배포 상태·Lambda 구성만 읽기 확인했다. 계정 식별자·도메인·인증 정보는 이 문서에 포함하지 않는다. 해당 서비스와 야구 서비스의 운영 리소스는 변경하지 않았다.

## 1. 기존 서비스는 고정 서버를 공유하는 구조가 아니다

기존 도서 서비스의 확인된 구성:

- 정적 웹: S3 + CloudFront
- API: HTTP API Gateway → Node.js 22 Lambda (x86_64, 256MB, 최대 20초)
- 크롤러: 별도 Lambda (2GB, 최대 90초), SQS FIFO + DLQ
- 저장: DynamoDB on-demand (`PAY_PER_REQUEST`)
- 운영: 일일 EventBridge 규칙, 7일 CloudWatch 로그, 배포 아티팩트 저장소
- 확인한 프로젝트 스택에는 EC2·Lightsail·RDS·NAT Gateway가 없다. Lambda도 VPC에 연결되어 있지 않다.

따라서 기존 월정액 서버의 남는 자원을 사용하는 효과는 없다. 같은 AWS 계정의 무료량·크레딧은 공유할 수 있지만 서비스별로 별도 무료량이 새로 생기는 것은 아니다. 재사용 효과는 배포 방식·IAM/OIDC 경험과 도구에 있으며, 앱 데이터·테이블·권한·로그는 분리하는 것이 적절하다. 기존 CloudFront나 API 경로를 무리하게 합쳐도 서버리스 컴퓨팅 요금이 없어지지 않는다.

실제 청구 총액·계정별 무료량 잔여분은 조회하지 않았다. 기존 앱은 최근 배포되었으므로 부분 월 사용액을 정상 운영 한 달 비용으로 간주하지 않는다.

## 2. 비용을 좌우하는 사용량 차이

기존 도서 서비스는 코드상 월 크롤링 10회 제한이 있다(관리자 예외 별도). 2GB로 매번 최대 90초를 사용한다고 가정하면 크롤러 계산량은 `10 × 2 × 90 = 1,800 GB-s`이다. 크롤러 Lambda 컴퓨팅만 약 **$0.03/월**, 요청 비용 별도다. 이는 서비스 전체 요금이 아니다.

야구는 경기 동안 반복 수집하므로 동일한 저빈도 서비스로 계산하면 안 된다. 계획 예시:

| 항목 | 가정 | 월 사용량 |
|---|---|---|
| 경기 수집 | 30일 × 5경기 × 4시간 × 60초 간격 | 36,000회 |
| 원본 요청 | 수집 1회당 HTTP 2개 | 72,000회 (일정·재시도 별도) |
| 수집 함수 | 512MB × 2초/회 | 36,000 GB-s |
| 앱 API | 하루 10,000회 × 30일, 512MB × 0.2초 | 300,000회 / 30,000 GB-s |

실제 경기일·사용자 수·새로고침 주기·DB 대기·콜드스타트에 따라 달라진다. 특히 이미지 크기·전송량과 원본 사이트의 허용 요청 빈도는 별도 확인해야 한다.

## 3. 서울 리전 서버리스 계산 예시

AWS 공개 Price List의 `ap-northeast-2` 현행 SKU를 직접 확인했다. 무료량·계정 크레딧 적용 전 계산이다.

| 비용 | 단가 | 위 가정의 월액 |
|---|---|---:|
| Lambda x86 컴퓨팅 | $0.0000166667/GB-s | 66,000 × 단가 = $1.10 |
| Lambda 요청 | $0.20/100만 회 | 336,000회 = $0.0672 |
| HTTP API Gateway | $1.23/100만 회, 첫 구간 | 300,000회 = $0.369 |
| **위 세 항목 합계** | DB·로그·전송 등 제외 | **약 $1.54** |

수집 스케줄러가 Lambda를 직접 호출한다는 가정이므로 수집 회차는 API Gateway 요청에 중복 계산하지 않았다. Scheduler, 로그, 이미지 저장·전송, 비밀값 저장, 이미지 레지스트리, 백업, 인증, 푸시 작업 및 세금은 별도다. Lambda 무료량이 충분하다면 컴퓨팅·요청 부분은 0이 될 수 있지만 계정 전체 사용량 확인 전 무료 운영을 보장하지 않는다.

DynamoDB로 저장소를 변경할 경우 서울 Standard on-demand 단가는 write unit 100만당 **$0.68**, read unit 100만당 **$0.1355**다. 예를 들어 월 180,000 write units + 300,000 read units는 약 **$0.163**이며 저장·백업 비용은 별도다. 항목 크기, 트랜잭션, 일관성 옵션, 인덱스에 따라 API 호출 1회와 request unit 1개는 같지 않다.

## 4. 야구 서비스 후보 비교

| 후보 | 월 비용 관점 | 코드/운영 영향 | 판단 |
|---|---|---|---|
| Lambda + HTTP API + MongoDB Atlas Free | 위 AWS 핵심 비용 약 $1.54 + 기타, DB $0 조건부 | FastAPI Lambda 어댑터·연결 재사용 검증 필요; 512MB 제한·백업 제약; 네트워크 정책 별도 | 기술 검증 후보. 운영 전체 무료로 확정하지 않음 |
| Lambda + HTTP API + Atlas Flex | 위 AWS 핵심 비용 + DB 약 $8~30/월 → **약 $9.54~31.54 + 기타** | 기존 Mongo 모델 유지 가능. Flex는 개발/테스트 지향; 운영 요건·연결 한도 확인 | 작은 앱도 DB가 컴퓨팅보다 큰 비용일 수 있음 |
| Lambda + HTTP API + DynamoDB | 위 가정의 핵심 컴퓨팅/API/DB 요청 합 약 **$1.70 + 저장·로그·전송 등** | Beanie/Mongo repository·쿼리·집계·테스트 재설계. 기존 도서 서비스의 인프라 패턴 활용 가능 | AWS 저고정비 우선이면 비교 가치 높음. 단순 호스팅 변경 아님 |
| Lightsail Linux IPv4 2GB/4GB + 자체 Mongo | 인스턴스 **$12/$24 월정액** + snapshot/백업 등 | 기존 FastAPI/Mongo 컨테이너 활용 가능. OS·TLS·DB 백업·복구·단일 장애 지점 직접 관리 | 비용 예측은 쉬우나 관리 부담 증가. 2GB 적합성은 부하 검증 필요 |
| 기존 Cloud Run 기준안 + Mongo | 이번 AWS 비교에서 재견적하지 않음 | 현재 컨테이너 배포 방식 유지; Mongo와 네트워크 비용은 여기서도 발생 | AWS가 무조건 더 싸다는 근거는 아직 없음 |

Atlas Free는 512MB 공유 환경이며 자동 백업 등 제한을 확인해야 한다. Atlas Dedicated는 공개 가격상 월 $56.94부터지만 서울 리전 실제 구성 가격은 별도다. AWS DocumentDB는 MongoDB와 동일 제품이 아니므로 가격·API 호환성 검증 없이 대체하지 않는다.

**중요한 비용 분기: MongoDB 접근 네트워크.** Lambda의 동적 출구 IP 때문에 고정 IP allowlist가 필요하면 VPC/NAT 등이 추가될 수 있다. NAT Gateway는 시간당 고정 요금과 처리량 요금이 발생한다. 공식 미국 리전 예시만으로도 $0.045 × 730시간 = **$32.85/월**이며 공인 IPv4·전송 비용이 더해질 수 있다. 서울 단가는 별도 재확인해야 한다. 따라서 위 Lambda+Atlas 숫자에 NAT 비용이 포함됐다고 해석하면 안 된다. 비용 절약을 위해 DB 접근을 무조건 전체 IP에 허용하는 구성도 자동 채택하지 않는다.

현재 FastAPI Docker 이미지를 Lambda에 그대로 지정해 실행할 수는 없다. Mangum 같은 ASGI 어댑터 또는 Lambda Web Adapter와 Lambda 런타임 패키징, 콜드스타트·DB 연결 수명·헬스 체크를 검증해야 한다. 경기 수집기는 예약 실행용 별도 handler/패키지와 시간 제한·중복 방지 설계가 필요하다. 위 비용 비교는 이 구현이 완료되었다는 의미가 아니다. DynamoDB는 승인되지 않은 비교 대안이며 비용만을 이유로 현재 MongoDB/Beanie를 교체하지 않는다.

## 5. 결론과 선택 전 확인

- 기존 도서 서비스의 저비용 핵심은 **저빈도 크롤링 + 요청 기반 Lambda/DynamoDB**다. 기존 고정 서버에 야구 API를 얹는 구조가 아니다.
- 야구를 AWS로 옮겨도 컴퓨팅은 작은 비용일 수 있지만, **MongoDB 요금·네트워크·개인 기록/통계의 저장 모델**이 선택을 좌우한다.
- 기존 코드를 최대한 유지하려면 MongoDB와 접근 정책의 실제 견적을 먼저 확정한다. 운영 편의까지 고려하면 Cloud Run과 AWS 중 어느 쪽이 싼지 아직 단정할 수 없다.
- AWS 저고정비가 최우선이면 DynamoDB 대안을 별도 설계·검증 대상으로 선택한다. 현재 앱/서버 기반 단계이므로 변경 검토는 가능하지만 저장 계층 재작성 비용을 명시한다.
- Lightsail은 $12~24 + 백업의 예측 가능한 대안이지만 서버·DB 관리 부담을 받아들일 때 선택한다.

최종 선택 전: 예상 활성 사용자·앱 폴링 간격, 경기별 실제 수집 실행시간, 원본 사용 조건, 보관 기간/이미지 트래픽, DB 백업 및 접근 정책, AWS 무료량/크레딧 잔여분을 확정한다. 본 문서는 비용 비교이며 유료 리소스 생성 승인이 아니다.

## 공식 출처

- [AWS Lambda 요금](https://aws.amazon.com/lambda/pricing/)
- [Lambda 서울 Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/ap-northeast-2/index.json)
- [API Gateway 서울 Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonApiGateway/current/ap-northeast-2/index.json)
- [DynamoDB 서울 Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/ap-northeast-2/index.json)
- [Lightsail 요금](https://aws.amazon.com/lightsail/pricing/)
- [MongoDB Atlas 요금](https://www.mongodb.com/pricing)
- [Atlas Free 제한](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)
- [NAT Gateway 과금](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html)
- [VPC 요금](https://aws.amazon.com/vpc/pricing/)
