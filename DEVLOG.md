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

## 2026-08-18 (X-Forwarded-For 위조로 인한 rate limit 완전 우회 버그 수정)
- 사용자 보고: 재배포 후 rate limit이 전혀 걸리지 않음. 5회 연속 POST가 전부 200으로 통과.
- 점검: `RateLimitMiddleware.dispatch`에 임시 `print` 로그를 추가해 로컬에서 카운터 값을
  직접 확인. 순수 로컬 요청(curl, 별도 헤더 없음)에서는 `minute_hits`가 0→1→2→3으로 정상
  증가하고 4번째 요청부터 429가 정확히 발생함을 확인 — `dispatch`의 early return/조건문
  자체에는 버그 없음.
- 원인 분리를 위해 `X-Forwarded-For` 헤더를 요청마다 다른 값으로 위조해서 재현 시도:
  ```
  curl -X POST ... -H "X-Forwarded-For: 10.0.0.$i" (i=1..5)
  ```
  → **5회 전부 200으로 통과, rate limit 완전 무력화 재현 성공.**
- 근본 원인: `_get_client_ip()`가 `X-Forwarded-For` 헤더 값을 무조건 신뢰하고 있었음.
  이 헤더는 클라이언트가 임의로 주입할 수 있는 값이라, 요청마다 다른 IP를 흉내내면 서버는
  매번 "새로운 IP의 첫 요청"으로 인식해 카운터가 절대 누적되지 않음. CLAUDE.md의
  "IP는 X-Forwarded-For 헤더에서 추출" 지침을 그대로 구현한 결과였으나, 실측 결과 신뢰할 수
  없는 헤더임이 확인됨.
- 수정: fly.io 엣지가 직접 설정하며 클라이언트가 위조할 수 없는 `Fly-Client-IP` 헤더를
  최우선으로 신뢰하도록 변경. 없을 때만 `X-Forwarded-For`로 폴백(로컬 개발 등 fly.io 프록시를
  거치지 않는 환경 대비), 그것도 없으면 remote address 사용. CLAUDE.md 보안 정책 절도 이
  우선순위로 갱신.
- 수정 후 재실측 (로컬, PORT=8128):
  - `X-Forwarded-For`만 요청마다 다르게 위조(`Fly-Client-IP` 없음) → 로컬 환경(= fly.io 프록시
    미경유) 특성상 여전히 5회 전부 200. **이 경로의 우회는 fly.io 배포 환경에서는 발생하지
    않음** — fly.io 엣지가 모든 요청에 `Fly-Client-IP`를 강제로 붙여주므로, 클라이언트가
    `X-Forwarded-For`를 위조해도 서버는 `Fly-Client-IP`를 우선 사용해 무시함. 로컬에서는 이
    헤더를 직접 시뮬레이션해야 검증 가능.
  - `Fly-Client-IP: 203.0.113.9` 고정값 + `X-Forwarded-For`를 매번 다르게 위조 → 1~3번째 200,
    4번째부터 429로 정상 동작 확인 (IP 스푸핑에 더 이상 영향받지 않음).
- 배포는 진행하지 않음 (로컬 코드 수정 + 로컬 재확인까지만). fly.io 재배포 후 실제
  `Fly-Client-IP` 헤더 기준으로 최종 동작을 한 번 더 확인 필요(사용자 배포 시 확인 권장).

## 2026-08-18 (재배포 후에도 rate limit 미작동 — 디버그 로그 추가 + uvicorn proxy_headers 점검)
- 사용자 보고: fly.io 재배포 후에도 rate limit이 전혀 걸리지 않음 (5회 연속 200).
- 조치: `_get_client_ip()`가 실제 어떤 값을 반환하는지 fly.io 환경에서 직접 확인할 수 없으므로,
  `RateLimitMiddleware.dispatch`에 매 요청마다 `fly-client-ip`/`x-forwarded-for` 원본 헤더값,
  `remote_addr`(request.client.host), 최종 채택된 IP, 카운터 상태(`minute_hits_before`,
  `daily_hits_before`)를 stdout으로 남기는 임시 디버그 로그 추가. 로컬 curl로 로그 정상
  출력 확인 후 커밋/push (b140c12). 배포는 사용자가 직접 진행, `fly logs`로 확인 예정.
- 병행 점검: uvicorn의 `--proxy-headers` 관련 동작이 `remote_addr`를 이미 오염시키고 있는지 확인.
  - FastMCP 소스(`fastmcp/server/mixins/transport.py`)에서 `mcp.run()`이 내부적으로
    `uvicorn.Config(app, host=host, port=port, **config_kwargs)`를 호출하며,
    `config_kwargs`에 `proxy_headers`/`forwarded_allow_ips`를 명시적으로 넘기지 않음을 확인
    (`server.py`의 `mcp.run()` 호출에도 해당 옵션 없음).
  - uvicorn 기본값 직접 확인(`uvicorn.Config` 인스턴스 생성 후 속성 조회):
    `proxy_headers=True`, `forwarded_allow_ips="127.0.0.1"`.
  - 의미: `proxy_headers=True`이므로 uvicorn은 **직전 홉의 소켓 IP가 `forwarded_allow_ips`
    (기본값 `127.0.0.1`) 목록에 있을 때만** `X-Forwarded-For` 헤더 값으로
    `request.client.host`를 덮어씀. fly.io 배포 환경에서 컨테이너로 들어오는 직전 홉(fly-proxy)의
    IP가 127.0.0.1이 아니라면 이 치환 자체가 발동하지 않아 `remote_addr`는 fly-proxy가 접속한
    원본 소켓 IP 그대로 남을 가능성이 큼 — 즉 우리 코드의 최후순위 fallback(`request.client.host`)이
    fly-proxy의 내부 IP로 고정되어 오히려 매번 "같은 IP"로 잡힐 개연성도 있음.
  - 다만 이 uvicorn 레벨 오염은 `_get_client_ip()`의 최우선 순위인 `fly-client-ip` 헤더 자체에는
    영향을 주지 않음(그 헤더는 애플리케이션 레벨에서 `request.headers`로 직접 읽으며, uvicorn이
    가공하는 대상이 아님) — 따라서 "재배포 후에도 전혀 안 걸림" 현상의 1차 용의선상은 여전히
    ① `fly-client-ip` 헤더가 이 fly.io 앱/네트워크 구성에서 실제로 전달되지 않는 경우,
    ② rate limit 인메모리 dict가 매 요청/배포마다 리셋되는 경우(멀티 머신 분산, 오토스케일 등),
    ③ 헤더 파싱 자체는 맞지만 다른 경로로 카운터가 항상 리셋되는 경우 세 가지로 좁혀짐.
    확정은 `fly logs`의 실제 로그 값 확인 후 가능 — 코드 수정은 보류하고 사용자 확인 대기.
- 결론: 코드 수정 없음(로그 추가만 커밋됨), 배포도 진행하지 않음. 사용자가 `fly logs`로
  `[ratelimit-debug]` 로그 라인을 확인해 `fly-client-ip`/`x-forwarded-for`/`remote_addr`/
  `resolved_ip` 값이 요청마다 어떻게 나오는지 확인 후 다음 조치 결정 예정.

## 2026-08-18 (최종 결론: IP 위조 문제 해결 확인, 멀티 머신 완화는 지침상 허용 트레이드오프로 수용)
- 사용자가 `fly logs`로 `[ratelimit-debug]` 로그를 직접 확인한 결과:
  - **IP 위조 문제는 해결됨**: 5회 연속 요청 모두 `resolved_ip=180.70.169.230`으로 정확히
    일치. `Fly-Client-IP` 헤더를 최우선 신뢰하도록 수정한 것이 fly.io 배포 환경에서 의도대로
    동작함이 실측으로 확인됨 (더 이상 요청마다 다른 IP로 오인되지 않음).
  - **재배포 후에도 5회 전부 200이 나왔던 이유**: fly.io가 요청을 2대 머신으로 분산시키고,
    `_minute_hits` 등 rate limit 카운터가 프로세스 인메모리(dict)라 머신마다 독립적으로 유지됨.
    같은 IP(`180.70.169.230`)의 요청이 머신 A/B에 번갈아 분산되면서, 각 머신에서는 카운터가
    "분당 3회 미만"으로 관측되어 통과됨. 결과적으로 동일 IP 기준 실질 제한이
    "분당 3회"가 아니라 **"분당 최대 6회(머신당 3회 × 2머신)"**로 완화됨.
  - 인메모리 카운터가 머신 간 공유되지 않는 것은 코드 결함이 아니라 CLAUDE.md 2-7절
    "멀티 머신 간 카운터 미공유 허용, 완벽한 전역 동기화 시도 금지" 지침에 이미 명시된
    설계상 트레이드오프. 외부 저장소(Redis 등) 도입 없이 in-memory로 구현하기로 한 결정의
    직접적인 귀결이며, 별도 수정이 필요한 버그가 아님.
- 사용자 결정: 이 완화(머신 수에 비례한 실질 제한 상승)를 문제 삼지 않고 현 상황을 그대로
  수용하기로 함. 추가 코드 수정 없음.
- 후속 조치:
  1. `RateLimitMiddleware`의 `[ratelimit-debug]` 임시 로그 제거 (원인 확인 완료, 더 이상 불필요).
  2. README.md의 rate limit 설명을 "분당 3회 (멀티 머신 배포 시 머신 수에 비례해 실질
     완화될 수 있음)"으로 갱신해 실제 배포 환경 동작과 문서를 일치시킴.
- 남은 이슈 없음. 이번 rate limit 점검 사이클(2번의 오탐 수정 + 1번의 설계상 트레이드오프
  확인)은 여기서 종료.
