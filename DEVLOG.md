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
