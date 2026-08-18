# DEVPLAN.md — 서울시 권역별 실시간 대기환경 현황 MCP

## 0. 개요
- **공공정보명(서비스명)**: 서울시 권역별 실시간 대기환경 현황
- **API 서비스명(SERVICE)**: `RealtimeCityAir`
- **제공기관/부서**: 서울특별시 기후환경본부 대기정책과 (담당자: 김정희, 02-2133-3665)
- **원본시스템**: 기후대기환경정보 서비스
- **플랫폼**: 서울 열린데이터광장 (openAPI.seoul.go.kr)
- **이용허락조건**: 공공누리 1유형 (출처표시, 상업적 이용 및 변경 가능)
- **저장소명(제안)**: `seoul-realtime-air-by-region-mcp`

기존에 이미 배포된 서울시 대기 관련 MCP들(자치구별, 측정소 원자료, 평균현황, 기간별 시간평균)과는
**"권역(SAREA_NM)" 단위**로 데이터를 제공한다는 점에서 구분된다. 서울시를 5개 권역
(도심권/동북권/동남권/서북권/서남권)으로 나눈 실시간 대기환경 현황과, 권역 내 개별 측정소 데이터를
함께 제공한다.

---

## 1. API 스펙 요약

### 1-1. 요청 URL 구조 (★실측 필요 — 1-1절 참고)
샘플 URL 기준 구조:
```
http://openAPI.seoul.go.kr:8088/{KEY}/{TYPE}/RealtimeCityAir/{START_INDEX}/{END_INDEX}/{SAREA_NM}/{MSRSTN_NM}
```
- 키(KEY)가 쿼리 파라미터가 아니라 **URL 경로 세그먼트**로 들어간다 (서울 열린데이터광장 공통 패턴).
- 실제 배포 시에는 `http://openAPI.seoul.go.kr:8088/` 대신 HTTPS 엔드포인트
  (`http://openapi.seoul.go.kr:8088/` 그대로 사용하거나, 실측 후 확정)를 사용한다.
- 선택 파라미터(SAREA_NM, MSRSTN_NM)는 **경로 뒤에 순서대로 추가**되는 방식으로 보인다
  (쿼리스트링이 아님). 즉 SAREA_NM만 쓰고 싶으면 `.../{END}/도심권`, 둘 다 쓰려면
  `.../{END}/동북권/성북구` 형태.

**요청 파라미터 상세**

| 변수 | 타입 | 필수여부 | 설명 |
|---|---|---|---|
| KEY | STRING | 필수 | 인증키 (경로 세그먼트로 추정, 실측 필요) |
| TYPE | STRING | 필수 | 응답 파일 타입: xml, xmlf, xls, json |
| SERVICE | STRING | 필수 | 고정값 `RealtimeCityAir` |
| START_INDEX | INTEGER | 필수 | 요청 시작 위치 (정수) |
| END_INDEX | INTEGER | 필수 | 요청 종료 위치 (정수) |
| SAREA_NM | STRING | 선택 | 권역명: 도심권, 동북권, 동남권, 서북권, 서남권 |
| MSRSTN_NM | STRING | 선택 | 측정소명 (예: 성북구) |

### 1-2. 응답 필드 (단위 포함)

| 순번 | 필드명 | 설명 | 단위 |
|---|---|---|---|
| 1 | MSRMT_DT | 측정일시 | YYYYMMDDHHmm |
| 3 | SAREA_NM | 권역명 | - |
| 5 | MSRSTN_NM | 측정소명 | - |
| 6 | PM | 미세먼지 | ㎍/㎥ |
| 7 | FPM | 초미세먼지농도 | ㎍/㎥ |
| 9 | OZON | 오존 | ppm |
| 10 | NTDX | 이산화질소농도 | ppm |
| 11 | CBMX | 일산화탄소농도 | ppm |
| 12 | SPDX | 아황산가스농도 | ppm |
| 13 | CAI_GRD | 통합대기환경등급 | 좋음/보통/나쁨/매우나쁨 등 |
| 14 | CAI_IDX | 통합대기환경지수 | 정수 |
| 15 | CRST_SBSTN | 지수결정물질 | 물질명(O3, PM10 등) |

※ 순번 2, 4, 8이 명세서에 없는 것은 명세서 원본 자체의 결번이며 정상이다 (list_total_count,
CODE, MESSAGE 등 메타 필드가 별도 위치에 있기 때문으로 추정 — 업로드된 응답 샘플에서 확인됨).

### 1-3. 에러 코드 체계

| 코드 | 의미 |
|---|---|
| INFO-000 | 정상 처리 |
| INFO-100 | 인증키 유효하지 않음 |
| INFO-200 | 해당 데이터 없음 |
| ERROR-300 | 필수 값 누락 |
| ERROR-301 | 파일타입(TYPE) 값 누락/유효하지 않음 |
| ERROR-310 | 해당 서비스(SERVICE) 없음 |
| ERROR-331 | START_INDEX 값 오류 |
| ERROR-332 | END_INDEX 값 오류 |
| ERROR-333 | 요청위치 값 타입 오류 (정수 아님) |
| ERROR-334 | END_INDEX < START_INDEX |
| ERROR-335 | 샘플키 사용 시 최대 5건 제한 |
| ERROR-336 | 한 번에 최대 1000건 제한 |
| ERROR-500 | 서버 오류 |
| ERROR-600 | DB 연결 오류 |
| ERROR-601 | SQL 오류 |

### 1-4. 페이징 방식
START_INDEX/END_INDEX 기반. 실측 전까지는 "정상적으로 START~END 범위를 반환한다"고 가정하되,
아래 실측 항목에서 실제 동작(다건 반환 여부)을 검증한다.

---

## 2. ★실측 필요 항목 (Claude Code가 반드시 코드로 검증 후 DEVLOG.md에 기록)

1. **키 위치**: 쿼리 파라미터(`?KEY=`)가 아니라 경로 세그먼트(`/{KEY}/...`)인지 확인.
   ERROR-300이 반복되면 이 문제부터 의심.
2. **선택 파라미터 결합 방식**: SAREA_NM/MSRSTN_NM이 정말 "경로에 순서대로 추가"되는 방식인지,
   아니면 쿼리 파라미터로도 받아주는지 실측. 특히 **SAREA_NM 없이 MSRSTN_NM만 쓰고 싶은 경우**
   (권역 생략, 측정소만 지정) 처리 방식이 명세서에 없으므로 실측 필요 — 안 되면 두 파라미터
   모두 있거나 모두 없는 조합만 지원하도록 서버 쪽에서 사전 검증.
3. **다건 조회 실제 동작**: START_INDEX=1, END_INDEX=25(측정소 전체 추정치) 요청 시 실제로
   여러 건이 반환되는지, 혹은 최신 1건만 오는지 확인.
4. **TYPE=json 요청 시 에러 응답이 XML로 오는 경우가 있는지**: 특히 SAREA_NM에 잘못된 값을
   넣었을 때(INFO-200) 응답 포맷 확인.
5. **list_total_count의 위치**: 업로드된 샘플 응답에서는 `<RealtimeCityAir><list_total_count>`
   최상위에 있고, `<RESULT><CODE>/<MESSAGE>`가 그 아래 형제 노드로 있음 — JSON 응답에서도
   동일 구조인지 실측.
6. **CAI_GRD 값의 실제 문자열 목록**: 업로드 샘플에는 "보통"만 확인됨. "좋음/보통/나쁨/매우나쁨"
   외 다른 표기(예: 영문, 숫자코드)가 없는지 실측 시 여러 시점 조회로 확인.

---

## 3. MCP 툴 설계 (최소 개수 원칙)

**2개 툴**로 구성 (권역 목록 조회는 고정값이므로 별도 툴 불필요, docstring에 명시):

### 3-1. `get_realtime_air_by_region`
- 설명: 권역별(또는 특정 권역/측정소) 실시간 대기환경 현황 조회
- 파라미터:
  - `sarea_nm` (optional, str): 권역명 — "도심권", "동북권", "동남권", "서북권", "서남권" 중 하나. 생략 시 전체 권역 반환.
  - `msrstn_nm` (optional, str): 측정소명. 생략 시 해당 권역 내 전체 측정소 반환.
  - `start_index`, `end_index` (optional, int): 기본값 1~50 정도로 설정 (실측 후 서울시 전체
    측정소 수에 맞춰 조정)
- 반환: 측정일시, 권역, 측정소, PM/FPM(㎍/㎥), OZON/NTDX/CBMX/SPDX(ppm), 통합대기환경등급/지수,
  지수결정물질

### 3-2. `list_available_regions`
- 설명: 조회 가능한 권역명 5개 고정 목록 반환 (도심권/동북권/동남권/서북권/서남권) —
  API 호출 없이 정적 데이터 반환. 사용자가 정확한 권역명을 모를 때 안내용.

---

## 4. 기술 스택
- Python 3.11+, FastMCP, httpx, python-dotenv
- 배포: fly.io (Docker), `stateless_http=True` 필수
- 인증키 없이 공개하므로 2-7절 3단계 rate limit 미들웨어 적용 대상

## 5. 디렉토리 구조
```
seoul-realtime-air-by-region-mcp/
├── server.py
├── seoul_api.py
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── fly.toml
├── README.md
├── DEVLOG.md
└── CLAUDE.md
```

## 6. 진행 순서
CLAUDE.md 2-4절 "작업 순서" 그대로 따름 (요구사항 → API 클라이언트 → 서버/rate limit →
env/gitignore → 로컬 실측 → 스모크 테스트 → Dockerfile/fly.toml → 문서 갱신 → commit/push → 정지)

## 7. 사용자가 먼저 할 일
1. 서울 열린데이터광장에서 "RealtimeCityAir" 서비스 활용신청 후 인증키 발급 (32자리 hex)
2. 이 문서 등 4종을 `C:\Users\hwang\Downloads\mcp-docs`에 저장 (본 응답 하단 안내 참고)
3. `run-new-mcp-project.bat -RepoName seoul-realtime-air-by-region-mcp -DocsPath "C:\Users\hwang\Downloads\mcp-docs"` 실행

## 8. 저장소 설명(Description 제안)
> 서울시 권역별(도심권/동북권/동남권/서북권/서남권) 실시간 대기환경 현황을 제공하는 MCP 서버 (서울 열린데이터광장 RealtimeCityAir API 기반)
