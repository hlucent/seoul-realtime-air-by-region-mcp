# CLAUDE.md — seoul-realtime-air-by-region-mcp

## 절대 규칙
- DEVPLAN.md 하나만 먼저 읽고 시작한다. 다른 문서 재탐색 금지.
- 웹서치 금지 (API 스펙은 DEVPLAN.md에 이미 있음).
- 불확실하면 추측성 재설계 대신 기본값 1개로 구현 후 DEVLOG.md에 "확인 필요"로 기록.
- 동일 오류 최대 3회까지만 재시도. 3회 실패 시 기록하고 사용자에게 보고.
- **역할은 "코드 구현 + 로컬 실측 테스트"까지다.** `fly launch`, `fly secrets set`,
  `flyctl deploy`, `fly logs` 등 fly.io 관련 명령은 절대 스스로 실행하지 않는다.
- 배포 준비(코드 구현, 로컬 테스트, git commit/push)가 끝나면 아래 "작업 순서"의 정지 시점에서
  멈추고, 사용자에게 "PowerShell 창에서 fly launch --no-deploy부터 진행하세요"라고 안내한다.

## 기술적으로 반드시 적용할 것

### `.env`
BOM 없는 UTF-8로 저장. python-dotenv가 BOM 있는 파일에서 키를 못 읽는 문제 재발 방지.

### `server.py`의 `mcp.run()`
```python
mcp.run(transport="streamable-http", host="0.0.0.0", port=port, stateless_http=True)
```
`stateless_http=True` 절대 누락 금지 — 없으면 fly.io 멀티머신 환경에서 세션 404, 커넥터에
"사용 가능한 도구 없음"으로 표시되는 문제가 재발한다.

### 응답 파싱: JSON 우선, XML 폴백 필수
정상 응답은 JSON이어도, 일부 에러 응답(INFO-100, INFO-200 등)이 TYPE=json 요청에도 XML로
돌아올 수 있다. `response.json()`이 실패하면 정규식으로 `<CODE>`/`<MESSAGE>` 패턴을 추출하는
폴백 파서를 반드시 구현한다.

```python
import re

def parse_response(text: str) -> dict:
    try:
        return json.loads(text)
    except ValueError:
        code_match = re.search(r"<CODE>(.*?)</CODE>", text)
        msg_match = re.search(r"<MESSAGE>(.*?)</MESSAGE>", text)
        return {
            "RESULT": {
                "CODE": code_match.group(1) if code_match else "UNKNOWN",
                "MESSAGE": msg_match.group(1) if msg_match else text[:200],
            }
        }
```

## API 키 취급 원칙
- 실제 키 값은 `os.environ`으로만 읽는다. 하드코딩 금지.
- `.env` 갱신 후 재테스트 전, 파일 크기/앞부분 문자열을 이전 값과 비교해 실제로 바뀌었는지 확인한다.
- 디버깅 시 키를 표준출력에 그대로 찍지 않는다. 필요하면 앞 4자리 + `...` + 길이만 출력.
- **키는 쿼리 파라미터가 아니라 URL 경로 세그먼트일 가능성이 높다** (DEVPLAN.md 1-1절 참고).
  실측 단계에서 경로 삽입 방식(`/{KEY}/json/RealtimeCityAir/...`)을 우선 시도하고,
  ERROR-300이 반복되면 다른 방식도 시도한다.

## 작업 순서

1. `requirements.txt` (fastmcp, httpx, python-dotenv)
2. `seoul_api.py` — API 호출 + 에러코드 매핑 (JSON 우선, XML 폴백 포함), 경로 세그먼트 방식 URL 빌더
3. `server.py` — 툴 2개 정의(docstring에 필드/단위 명시), `stateless_http=True` 필수,
   아래 "rate limit 미들웨어" 포함
4. `.env.example`, `.gitignore`
5. 로컬 테스트 (실제 키로 각 툴 호출):
   - URL 구조(키의 위치: 쿼리 vs 경로)부터 확인. ERROR-300 반복 시 키 위치 의심.
   - SAREA_NM/MSRSTN_NM 조합별 실측: 둘 다 생략, SAREA_NM만, 둘 다 지정, MSRSTN_NM만
     (권역 생략) — 각각 정상 동작하는지 확인 후 DEVPLAN.md 2절 "실측 필요 항목" 결과를
     DEVLOG.md에 기록
   - START_INDEX/END_INDEX 범위를 넓혀 실제 여러 건이 반환되는지 확인
6. FastMCP 서버 스모크 테스트 (initialize 요청까지만)
7. `Dockerfile`, `fly.toml` — **아래 "표준 fly.toml 템플릿" 그대로 사용, fly launch의 자동
   생성을 기다리지 않는다.**
8. README/DEVLOG 갱신 — 실측으로 확인된 제약사항을 실제 동작 기준으로 정확히 기술
9. `git add/commit/push`까지 수행 (push는 자동 진행 가능 — 백업 목적, 실제 배포와 무관)
10. **여기서 정지** — 사용자에게 PowerShell에서 `fly launch --no-deploy`부터 진행하도록 안내

## 하지 말 것
- 툴 개수를 DEVPLAN 범위(2개)보다 늘리지 않기
- 인증키 하드코딩 금지
- `stateless_http=True` 누락 금지
- `fly launch` / `fly secrets set` / `flyctl deploy` / `fly logs` 자동 실행 금지
- rate limit 미들웨어 누락 금지
- fly.toml을 구버전 `[[services]]` 방식으로 두지 않기 (아래 표준 템플릿 사용)

## 표준 fly.toml 템플릿 (그대로 사용, 앱 이름만 치환)

```toml
app = 'seoul-realtime-air-by-region-mcp'
primary_region = 'nrt'

[build]
  dockerfile = 'Dockerfile'

[env]
  PORT = '8000'

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = 'connections'
    hard_limit = 256
    soft_limit = 200

[[vm]]
  memory = '1gb'
  cpu_kind = 'shared'
  cpus = 1
  memory_mb = 1024
```

## 실측 필요 항목 처리 절차 (명세서와 실제 동작이 다를 때)
1. 같은 조건으로 최소 2회 재현 확인 (우연 배제)
2. 원인 분리 (코드 문제 vs API 자체 특이 동작) — sample 키나 원시 URL 호출로 최소 재현
3. 코드 레벨에서 검증 가능한 가설(키 위치, URL 인코딩, 파라미터 조합)을 3회 재시도 원칙 안에서 순서대로 검증
4. DEVLOG.md에 시도/확인/미확인 내용 명확히 기록
5. 발견된 제약을 클라이언트 코드가 API 호출 전에 걸러서 명확한 에러로 안내하도록 사전 검증 로직 추가
6. README.md/DEVPLAN.md를 실제 동작 기준으로 갱신 (커밋 대상 포함)

## MCP 서버 보안 정책 (API 키 없이 공개 — 이 프로젝트는 해당)

**반드시** 3단계 IP 기반 rate limit 적용:
1. 분당 호출 제한: 같은 IP 1분 슬라이딩 윈도우 내 3회 초과 시 429
2. 반복 위반 시 임시 차단: 1시간 내 429를 5회 이상 받은 IP는 24시간 차단
3. 일일 총량 제한: IP당 24시간 rolling 기준 총 30회 초과 시 429

구현 원칙:
- in-memory(dict) 저장으로 충분, 외부 저장소 도입 금지
- IP는 `X-Forwarded-For` 헤더에서 추출, 없으면 remote address 사용
- 429 응답에 원인 메시지 포함 (예: "Rate limit exceeded. Try again later.")
- `stateless_http=True`와 무관하게 유지 — 멀티 머신 간 카운터 미공유 허용, 완벽한 전역 동기화 시도 금지
- FastMCP + Starlette: `BaseHTTPMiddleware` 서브클래싱 후
  `mcp.run(..., middleware=[Middleware(RateLimitMiddleware)])` 형태로 `starlette.middleware.Middleware`로
  감싸서 전달 (클래스를 직접 리스트에 넣으면 타입 오류)
- 작업 순서 3번 단계에서 함께 구현

## 파일 편집 승인
매 파일 생성마다 개별 승인이 반복되면, 사용자에게 "이번 세션 전체 편집 허용"으로 전환하도록
첫 승인 시점에 안내한다. 단, 실제 API 키로 네트워크 호출하는 `python -c` 류는 매번 개별 확인 권장.
