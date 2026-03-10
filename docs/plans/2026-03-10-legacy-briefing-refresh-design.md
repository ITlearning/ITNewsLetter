# Legacy Briefing Refresh Design

## Goal
- 이전 plain-text `detailed_summary`를 새 humanized markdown 브리핑으로 자연스럽게 전환한다.
- 이미 저장된 데이터를 전부 지우지 않고, lazy 재생성이 가능한 항목만 안전하게 비운다.

## Options
### 1. 전체 `detailed_summary` 삭제
- 장점: 단순하다.
- 단점: GeekNews나 lazy 미지원 항목까지 잃는다.

### 2. Redis 캐시만 비우기
- 장점: 서버 캐시만 정리하면 된다.
- 단점: `data/news.json`에 남아 있는 legacy 브리핑은 그대로여서 상세 페이지가 재생성되지 않는다.

### 3. 선별 정리 + 캐시 버전 bump
- 장점: lazy 재생성이 가능한 legacy 항목만 새 형식으로 유도할 수 있다.
- 단점: 선별 기준과 one-off 스크립트가 필요하다.

## Decision
- 3번을 선택한다.
- 선별 기준:
  - `detailed_summary`가 존재한다.
  - 제한 Markdown 구조로 보이지 않는다.
  - `detailed_summary`를 제거했을 때 lazy detail 정책상 다시 생성 가능한 항목이다.
- lazy Redis 캐시는 key prefix를 `v2`로 올려 기존 생성 캐시를 무효화한다.

## Files
- `scripts/fetch_and_send.py`
- `scripts/reset_legacy_briefings.py`
- `api/_lib/lazy-detail-cache.mjs`
- `README.md`
- `tests/test_fetch_and_send_enrichment.py`
- `tests/test_reset_legacy_briefings.py`
