"""서울 열린데이터광장 RealtimeCityAir API 클라이언트."""

import json
import os
import re

import httpx

BASE_URL = "http://openapi.seoul.go.kr:8088"
SERVICE = "RealtimeCityAir"

ERROR_MESSAGES = {
    "INFO-000": "정상 처리",
    "INFO-100": "인증키가 유효하지 않습니다.",
    "INFO-200": "해당 조건의 데이터가 없습니다.",
    "ERROR-300": "필수 요청 값이 누락되었습니다.",
    "ERROR-301": "TYPE 값이 누락되었거나 유효하지 않습니다.",
    "ERROR-310": "해당 서비스(SERVICE)가 존재하지 않습니다.",
    "ERROR-331": "START_INDEX 값이 유효하지 않습니다.",
    "ERROR-332": "END_INDEX 값이 유효하지 않습니다.",
    "ERROR-333": "요청 위치(INDEX) 값이 정수가 아닙니다.",
    "ERROR-334": "END_INDEX가 START_INDEX보다 작습니다.",
    "ERROR-335": "샘플 인증키는 최대 5건까지만 요청할 수 있습니다.",
    "ERROR-336": "한 번에 최대 1000건까지 요청할 수 있습니다.",
    "ERROR-500": "서버 오류가 발생했습니다.",
    "ERROR-600": "데이터베이스 연결 오류가 발생했습니다.",
    "ERROR-601": "SQL 오류가 발생했습니다.",
}


VALID_SAREA_NM = {"도심권", "동북권", "동남권", "서북권", "서남권"}


class SeoulApiError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def parse_response(text: str) -> dict:
    """JSON 우선 파싱, 실패 시 XML(<CODE>/<MESSAGE>) 폴백 파서."""
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


def build_url(
    start_index: int,
    end_index: int,
    sarea_nm: str | None = None,
    msrstn_nm: str | None = None,
) -> str:
    """키를 경로 세그먼트로 삽입하는 URL 빌더 (DEVPLAN.md 1-1절)."""
    api_key = os.environ["SEOUL_API_KEY"]
    segments = [BASE_URL, api_key, "json", SERVICE, str(start_index), str(end_index)]
    if sarea_nm:
        segments.append(sarea_nm)
    if msrstn_nm:
        segments.append(msrstn_nm)
    return "/".join(segments)


async def fetch_realtime_air(
    start_index: int,
    end_index: int,
    sarea_nm: str | None = None,
    msrstn_nm: str | None = None,
) -> dict:
    # 실측 확인: MSRSTN_NM은 경로상 SAREA_NM 다음 자리이므로, SAREA_NM 없이
    # MSRSTN_NM만 넘기면 그 값이 SAREA_NM 자리로 해석되어 INFO-200이 발생한다.
    if msrstn_nm and not sarea_nm:
        raise SeoulApiError(
            "CLIENT-VALIDATION",
            "msrstn_nm을 지정하려면 sarea_nm도 함께 지정해야 합니다 (API 제약).",
        )
    if sarea_nm and sarea_nm not in VALID_SAREA_NM:
        raise SeoulApiError(
            "CLIENT-VALIDATION",
            f"sarea_nm은 {sorted(VALID_SAREA_NM)} 중 하나여야 합니다.",
        )

    url = build_url(start_index, end_index, sarea_nm, msrstn_nm)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
    resp.encoding = "utf-8"
    data = parse_response(resp.text)

    result_node = data.get(SERVICE, {}).get("RESULT") if SERVICE in data else data.get("RESULT")
    if result_node is None:
        raise SeoulApiError("UNKNOWN", "응답 형식을 해석할 수 없습니다.")

    code = result_node.get("CODE", "UNKNOWN")
    if code != "INFO-000":
        message = result_node.get("MESSAGE") or ERROR_MESSAGES.get(code, "알 수 없는 오류")
        raise SeoulApiError(code, message)

    return data
