# DEVLOG.md — seoul-realtime-air-by-region-mcp

기록 형식:
```
## YYYY-MM-DD
- 무엇을 했는지
- 무엇을 확인했는지 (실측 결과 포함)
- 무엇이 아직 미확인/확인 필요인지
```

---

## 2026-08-18
- DEVPLAN.md/CLAUDE.md/README.md/DEVLOG.md 4종 문서 작성 완료 (Claude 웹챗, 업로드된
  명세서 `서울시_권역별_실시간_대기환경_현황.xls` 기반 분석).
- 확인된 사항: 서비스명 `RealtimeCityAir`, 응답 필드 12개(단위 포함), 에러코드 체계,
  샘플 URL 구조(`/{KEY}/{TYPE}/RealtimeCityAir/{START}/{END}/{SAREA_NM}/{MSRSTN_NM}`).
- 미확인(실측 필요, DEVPLAN.md 2절 참고):
  1. 키가 실제로 경로 세그먼트인지
  2. SAREA_NM/MSRSTN_NM 조합별 처리 방식 (특히 MSRSTN_NM만 쓰고 SAREA_NM 생략 가능한지)
  3. START_INDEX/END_INDEX로 실제 다건 반환되는지
  4. TYPE=json 요청 시 에러 응답이 XML로 오는 경우가 있는지
  5. list_total_count/RESULT 노드 위치가 JSON에서도 동일한지
  6. CAI_GRD 값의 전체 목록
- 다음 단계: Claude Code가 CLAUDE.md 기준으로 구현 및 로컬 실측 테스트 진행 예정.

## 2026-08-18 (구현 및 실측)
- `requirements.txt`, `seoul_api.py`, `server.py`, `Dockerfile`, `fly.toml` 작성 완료.
- 실측 결과 (DEVPLAN.md 2절 대응):
  1. **키 위치**: 경로 세그먼트(`/{KEY}/json/RealtimeCityAir/...`) 방식 확인. 정상 동작.
  2. **SAREA_NM/MSRSTN_NM 조합**:
     - SAREA_NM만 지정 → 정상 (해당 권역 내 측정소 목록 반환)
     - SAREA_NM + MSRSTN_NM 둘 다 지정 → 정상 (단일 측정소 반환)
     - **MSRSTN_NM만 지정(SAREA_NM 생략) → INFO-200(데이터 없음)**. 경로상 선택 파라미터
       순서가 SAREA_NM → MSRSTN_NM으로 고정되어 있어, SAREA_NM 자리에 측정소명이 들어가면서
       실패하는 것으로 확인. `seoul_api.py`에서 API 호출 전 사전 검증으로 차단하도록 구현.
  3. **다건 조회**: START_INDEX=1, END_INDEX=25 요청 시 실제 25건 전부 반환 확인
     (list_total_count=25와 일치).
  4. **TYPE=json 요청의 XML 에러 응답**: 잘못된 인증키(INFO-100) 요청 시 JSON이 아닌 XML
     (`<RESULT><CODE>INFO-100</CODE><MESSAGE><![CDATA[...]]></MESSAGE></RESULT>`)로 응답함을
     확인. `parse_response()`의 XML 폴백 파서가 정상 동작함을 실측으로 검증.
  5. **list_total_count/RESULT 위치**: JSON 정상 응답에서는
     `{"RealtimeCityAir": {"list_total_count": ..., "RESULT": {...}, "row": [...]}}` 구조.
     에러 응답(INFO-200, ERROR-334 등)에서는 `RealtimeCityAir` 래퍼 없이 최상위
     `{"RESULT": {...}}`만 반환됨을 확인 — `seoul_api.py`에서 두 구조 모두 처리하도록 구현.
  6. **CAI_GRD 값 목록**: 실측 시점(2026-08-18 22시) 25건 조회 결과 "좋음", "보통" 2종 확인.
     "나쁨"/"매우나쁨"은 이번 실측에서는 관측되지 않음 (대기 상태에 따라 달라지므로 미확인으로 유지).
  7. 응답 인코딩: 서버가 `charset=UTF-8` 헤더를 보내지만 httpx가 기본 감지한 인코딩과 실제
     바이트가 불일치하는 경우가 있어, `resp.encoding = "utf-8"`을 명시적으로 강제해 처리함.
- FastMCP 서버 스모크 테스트(initialize 요청) 성공, `stateless_http=True` 반영 확인.
- rate limit 미들웨어(분당 3회/시간당 5회 위반 시 24시간 차단/일 30회) 구현 완료.
- 확인 필요(추측 미해결): 없음 — DEVPLAN.md 2절 6개 항목 모두 실측 완료.
- 다음 단계: git add/commit/push 후 사용자에게 `fly launch --no-deploy`부터 안내.

## 2026-08-18 (rate limit 버그 수정)
- 사용자 보고: 분당 3회 제한인데 실제로는 2번째 요청부터 429가 뜸.
- 원인 분리: `RateLimitMiddleware.dispatch`가 메서드 구분 없이 모든 요청을 카운트하고 있었음.
  MCP 클라이언트가 실제 POST 전에 CORS preflight `OPTIONS` 요청을 함께 보내면, 요청 1건당
  카운터가 2씩(`OPTIONS` + `POST`) 올라가 "분당 3회" 제한이 실질적으로 "실 요청 1.5회" 수준으로
  동작함을 로컬 curl 재현으로 확인.
- 수정 전 실측 (curl, `Origin`/`Access-Control-Request-Method` 헤더 포함 OPTIONS 4회 연속):
  각 OPTIONS 호출이 `_minute_hits`에 그대로 적재되어, 뒤이은 실제 POST 요청이 조기에 429 처리됨.
- 수정 내용: `dispatch` 최상단에서 `request.method == "OPTIONS"`이면 카운팅 없이 즉시
  `call_next(request)`로 통과.
- 수정 후 재실측 (로컬, PORT=8125):
  - OPTIONS 5회 연속 호출 → 전부 429 없음 (라우트 미지원으로 405, rate limit 카운터엔 영향 없음 확인)
  - POST(initialize) 4회 연속 호출 → 1~3번째 200, 4번째 429로 "분당 3회 초과 시 429" 사양과 일치
- 배포는 진행하지 않음 (로컬 코드 수정 + 로컬 재확인까지만).
