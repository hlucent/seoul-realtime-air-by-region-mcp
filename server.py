"""서울시 권역별 실시간 대기환경 현황 MCP 서버."""

import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from seoul_api import SeoulApiError, VALID_SAREA_NM, fetch_realtime_air

load_dotenv()

mcp = FastMCP("seoul-realtime-air-by-region-mcp")

REGION_LIST = ["도심권", "동북권", "동남권", "서북권", "서남권"]

RESPONSE_FIELDS = [
    "MSRMT_DT",
    "SAREA_NM",
    "MSRSTN_NM",
    "PM",
    "FPM",
    "OZON",
    "NTDX",
    "CBMX",
    "SPDX",
    "CAI_GRD",
    "CAI_IDX",
    "CRST_SBSTN",
]


@mcp.tool()
async def get_realtime_air_by_region(
    sarea_nm: str | None = None,
    msrstn_nm: str | None = None,
    start_index: int = 1,
    end_index: int = 25,
) -> dict:
    """서울시 권역별(또는 특정 권역/측정소) 실시간 대기환경 현황을 조회합니다.

    Args:
        sarea_nm: 권역명 — "도심권", "동북권", "동남권", "서북권", "서남권" 중 하나.
            생략 시 서울시 전체 권역을 반환합니다.
        msrstn_nm: 측정소명(예: "중구"). 지정하려면 sarea_nm도 함께 지정해야 합니다
            (API 제약 — sarea_nm 없이 msrstn_nm만 넘기면 데이터 없음으로 처리됨).
        start_index: 조회 시작 위치 (1부터 시작). 기본값 1.
        end_index: 조회 종료 위치. 기본값 25 (서울시 전체 측정소 수).

    Returns:
        측정일시(MSRMT_DT, YYYYMMDDHHmm), 권역(SAREA_NM), 측정소(MSRSTN_NM),
        미세먼지(PM, ㎍/㎥), 초미세먼지(FPM, ㎍/㎥), 오존(OZON, ppm),
        이산화질소농도(NTDX, ppm), 일산화탄소농도(CBMX, ppm), 아황산가스농도(SPDX, ppm),
        통합대기환경등급(CAI_GRD, 예: 좋음/보통), 통합대기환경지수(CAI_IDX),
        지수결정물질(CRST_SBSTN)을 포함한 측정소별 목록.
    """
    try:
        data = await fetch_realtime_air(start_index, end_index, sarea_nm, msrstn_nm)
    except SeoulApiError as e:
        return {"error": True, "code": e.code, "message": e.message}

    payload = data.get("RealtimeCityAir", data)
    return {
        "total_count": payload.get("list_total_count"),
        "rows": payload.get("row", []),
    }


@mcp.tool()
def list_available_regions() -> dict:
    """조회 가능한 서울시 권역명 5개 고정 목록을 반환합니다 (API 호출 없음).

    Returns:
        도심권/동북권/동남권/서북권/서남권 5개 권역명 목록.
        get_realtime_air_by_region의 sarea_nm 파라미터에 사용할 정확한 값을 확인할 때 사용합니다.
    """
    return {"regions": REGION_LIST}


# --- Rate limit 미들웨어 (CLAUDE.md 보안 정책) ---
_minute_hits: dict[str, list[float]] = defaultdict(list)
_daily_hits: dict[str, list[float]] = defaultdict(list)
_violations: dict[str, list[float]] = defaultdict(list)
_blocked_until: dict[str, float] = {}

MINUTE_LIMIT = 3
DAILY_LIMIT = 30
VIOLATION_LIMIT = 5
VIOLATION_WINDOW = 3600
BLOCK_DURATION = 86400


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = _get_client_ip(request)
        now = time.time()

        blocked_at = _blocked_until.get(ip)
        if blocked_at and now < blocked_at:
            return JSONResponse(
                {"error": "Rate limit exceeded. Try again later. (temporarily blocked)"},
                status_code=429,
            )

        _minute_hits[ip] = [t for t in _minute_hits[ip] if now - t < 60]
        _daily_hits[ip] = [t for t in _daily_hits[ip] if now - t < 86400]
        _violations[ip] = [t for t in _violations[ip] if now - t < VIOLATION_WINDOW]

        if len(_minute_hits[ip]) >= MINUTE_LIMIT or len(_daily_hits[ip]) >= DAILY_LIMIT:
            _violations[ip].append(now)
            if len(_violations[ip]) >= VIOLATION_LIMIT:
                _blocked_until[ip] = now + BLOCK_DURATION
            return JSONResponse(
                {"error": "Rate limit exceeded. Try again later."},
                status_code=429,
            )

        _minute_hits[ip].append(now)
        _daily_hits[ip].append(now)
        return await call_next(request)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        stateless_http=True,
        middleware=[Middleware(RateLimitMiddleware)],
    )
