# seoul-realtime-air-by-region-mcp

서울시 권역별(도심권/동북권/동남권/서북권/서남권) 실시간 대기환경 현황을 조회하는 MCP 서버입니다.
서울 열린데이터광장의 `RealtimeCityAir` API를 기반으로 합니다.

- **제공기관/부서**: 서울특별시 기후환경본부 대기정책과
- **원본 데이터**: [서울 열린데이터광장 — 서울시 권역별 실시간 대기환경 현황](https://data.seoul.go.kr/)
- **라이선스(데이터)**: 공공누리 1유형 (출처표시, 상업적 이용 및 변경 가능)
- **라이선스(코드)**: MIT

## 제공 툴

### `get_realtime_air_by_region`
권역별(또는 특정 권역/측정소) 실시간 대기환경 현황을 조회합니다.

| 파라미터 | 필수 | 설명 |
|---|---|---|
| `sarea_nm` | 선택 | 권역명 — 도심권/동북권/동남권/서북권/서남권 중 하나. 생략 시 전체 권역 |
| `msrstn_nm` | 선택 | 측정소명. **`sarea_nm` 없이 단독 사용 불가** (아래 제약사항 참고) |
| `start_index`, `end_index` | 선택 | 조회 범위 (기본값 1~25, 서울시 전체 측정소 수 기준) |

반환 필드: 측정일시(MSRMT_DT), 권역(SAREA_NM), 측정소(MSRSTN_NM), 미세먼지(PM, ㎍/㎥),
초미세먼지(FPM, ㎍/㎥), 오존(OZON, ppm), 이산화질소(NTDX, ppm), 일산화탄소(CBMX, ppm),
아황산가스(SPDX, ppm), 통합대기환경등급(CAI_GRD), 통합대기환경지수(CAI_IDX), 지수결정물질(CRST_SBSTN)

### `list_available_regions`
조회 가능한 권역명 5개(도심권/동북권/동남권/서북권/서남권) 고정 목록을 반환합니다. API 호출 없음.

## 실측으로 확인된 제약사항

- **인증키는 URL 경로 세그먼트**로 전달합니다 (`/{KEY}/json/RealtimeCityAir/...`), 쿼리 파라미터가 아닙니다.
- **`msrstn_nm`은 `sarea_nm` 없이 단독으로 사용할 수 없습니다.** API 경로 구조상 선택 파라미터는
  `SAREA_NM` 자리 → `MSRSTN_NM` 자리 순서로 고정되어 있어, `sarea_nm`을 생략하고 `msrstn_nm`만
  넘기면 그 값이 `SAREA_NM` 자리로 해석되어 `INFO-200`(데이터 없음)이 반환됩니다. 이 서버는
  `msrstn_nm`만 지정된 요청을 API 호출 전에 걸러 명확한 에러로 안내합니다.
- `start_index`/`end_index` 범위를 넓히면 실제로 여러 건이 정상 반환됩니다 (전체 조회 시 25건 확인).
- 정상 응답은 JSON이지만, **인증키 오류(INFO-100) 등 일부 에러 응답은 TYPE=json 요청에도 XML로
  돌아옵니다.** 이 서버는 JSON 파싱 실패 시 XML `<CODE>`/`<MESSAGE>`를 추출하는 폴백 파서를 사용합니다.
- `CAI_GRD`(통합대기환경등급) 값은 실측 시점 기준 "좋음", "보통"이 확인되었습니다("나쁨"/"매우나쁨"은
  실측 시점에 관측되지 않았으나 명세상 존재 가능).

## 설치 및 실행 (로컬)

```bash
git clone https://github.com/hlucent/seoul-realtime-air-by-region-mcp.git
cd seoul-realtime-air-by-region-mcp
pip install -r requirements.txt
cp .env.example .env  # SEOUL_API_KEY 값 입력
python server.py
```

## 환경변수

| 변수명 | 설명 |
|---|---|
| `SEOUL_API_KEY` | 서울 열린데이터광장에서 발급받은 인증키 |
| `PORT` | 서버 포트 (fly.io 배포 시 기본 8000) |

## 배포 (fly.io)

```bash
fly launch --no-deploy
fly secrets set SEOUL_API_KEY=<발급받은키>
flyctl deploy
```

배포 후 Claude.ai 커넥터 연결 시 아래 형태로 `/mcp` 경로를 붙여 등록합니다:
```
https://<앱이름>.fly.dev/mcp
```

## 보안

인증키 없이 공개되는 서버로, IP 기반 3단계 rate limit이 적용되어 있습니다
(분당 3회, 시간당 5회 위반 시 24시간 차단, 일 30회 총량 제한).

## 라이선스

MIT License. 원본 데이터는 공공누리 1유형을 따릅니다.
