# 뉴스룸/발송정책/AI 고도화 설계

- 작성일: 2026-03-05
- 범위: Anthropic 공식 뉴스룸 소스 추가 + 발송 정책 고도화 + AI 활용 확장
- 상태: 사용자 승인 완료 (단, `quiet hours` 기능은 제외)

## 1. 확정 요구사항

- Anthropic 공식 뉴스룸도 수집한다.
- 발송 주기는 `90분마다` 동작하고, 1회 `3개`를 기본으로 한다.
- 하루 총 발송은 `30~40개` 목표(soft cap)로 운영한다.
- `quiet hours`(예: 23:00~07:00 무음)는 적용하지 않는다.
- 아침 브리핑은 `07:00 KST`에 `Digest 1개 + 일반 뉴스 1개`로 보낸다.
- Digest에는 상위 `5개`를 포함한다.
- 기존 정책(GeekNews 우선, 3일 초과 제외)은 유지한다.

## 2. 접근 방식 비교

### A. 워크플로우 크론만 조정
- 장점: 변경이 가장 작다.
- 단점: 90분 정책, 아침 Digest, soft cap을 정교하게 표현하기 어렵다.

### B. 스크립트 내부 정책 엔진 확장 (채택)
- 장점: 시간/수량/우선순위 정책을 코드 한 곳에서 제어 가능하다.
- 장점: 현재 상태파일(`state.json`) 기반 구조와 가장 잘 맞는다.
- 단점: 상태 스키마가 확장되고 테스트 항목이 늘어난다.

### C. 별도 큐/스토리지 도입
- 장점: 확장성 높음.
- 단점: 현 단계에서 과도한 복잡도(YAGNI 위반 가능).

## 3. 아키텍처 변경안

### 3.1 소스 수집 계층
- 기존 `rss` + 신규 `sitemap` 모드를 사용한다.
- Anthropic Engineering은 이미 `path_prefix=/engineering`로 수집 중이다.
- Anthropic Newsroom을 `path_prefix=/news`로 동일한 방식으로 추가한다.

### 3.2 발송 정책 계층
- 워크플로우는 30분 간격 실행(수집 안정성 확보).
- 스크립트는 `last_normal_dispatch_at`을 기준으로 90분 게이트를 적용한다.
- 07:00 KST에 하루 1회 아침 브리핑 전송 여부를 판단한다.

### 3.3 큐/상태 관리
- 후보 뉴스는 기존 dedupe 후 `pending queue`에 병합한다.
- 전송 성공 시 즉시 상태 반영(중복 전송 방지).

## 4. 상태 스키마 설계 (`data/state.json`)

```json
{
  "sent_ids": {
    "sha1-id": 1760000000
  },
  "dispatch": {
    "last_normal_dispatch_at": "2026-03-05T00:00:00+00:00",
    "last_digest_date_kst": "2026-03-05",
    "daily_date_kst": "2026-03-05",
    "daily_sent_count": 18
  },
  "pending_items": [
    {
      "id": "sha1-id",
      "source": "GeekNews",
      "title": "...",
      "link": "...",
      "published_at": "...",
      "priority_score": "..."
    }
  ]
}
```

## 5. 발송 정책 상세

### 5.1 평시 발송
- 조건: `now - last_normal_dispatch_at >= 90분`
- 수량: 최대 3개
- 선택 순서:
  1. GeekNews 우선
  2. 부족분은 기술/일반 우선순위로 채움

### 5.2 아침 브리핑 (`07:00 KST`)
- 조건: `last_digest_date_kst != today_kst`
- 전송:
  1. Digest 1개(상위 5개 요약)
  2. 일반 뉴스 1개(기존 카드 포맷)

### 5.3 Soft Cap (`30~40/day`)
- 기본 목표: 일일 36개(중심값) 운영
- 소프트 상한: 40개
- 상한 도달 시:
  - 일반/저우선 뉴스는 지연(큐에 유지)
  - GeekNews/고우선 기술 글은 제한적으로 예외 허용

## 6. 시간대 정책

- `quiet hours`는 적용하지 않는다.
- 이유: 단일 Discord 채널에 다중 시간대 사용자(예: KST + US)가 존재함.
- 결과: 시간대 무음 대신 `90분 게이트 + soft cap + 아침 Digest`로 과다 알림을 제어한다.

## 7. 오류 처리

- 소스별 수집 실패는 런 전체 실패로 전파하지 않고 `source_failures`에 누적한다.
- Digest 생성 실패 시 fallback:
  - 일반 뉴스 1개만 전송하고 다음 런에서 재시도
- 상태 파일 쓰기 실패 시 런을 실패 처리해 중복 전송 리스크를 낮춘다.

## 8. 테스트 전략

### 단위 테스트
- KST 날짜/시간 계산(특히 07:00 경계)
- 90분 게이트 동작
- daily counter reset (KST 날짜 전환)
- soft cap 예외 허용 조건
- sitemap path_prefix 필터(`/news`, `/engineering`)

### 통합 테스트
- `DRY_RUN=1`로 시나리오 재현:
  - normal dispatch
  - morning digest
  - soft cap 초과 케이스

## 9. 단계별 구현 계획(요약)

1. `config/sources.yaml`에 Anthropic Newsroom 소스 추가
2. `state.json` 확장 필드 읽기/쓰기 구현
3. dispatch policy 함수 분리(90분/07:00/soft cap)
4. digest message formatter 추가
5. 로그/요약 필드 추가(`digest_sent`, `daily_sent_count`, `pending_total`)
6. 회귀 테스트 + DRY_RUN 검증

## 10. AI 활용 확장안

- Digest 자동 요약 강화:
  - 5개 기사 공통 맥락 1~2문장 생성
  - 각 기사 핵심 포인트 1줄 생성
- 유사 기사 클러스터링:
  - 동일 이슈 기사 중복 노출 축소
- 기술 가치 스코어 강화:
  - 코드 링크/실사용 사례/벤치마크 포함 기사 가점

## 11. 비목표(이번 범위 제외)

- 사용자별 시간대 무음(채널 단위 한계)
- 별도 DB/메시지 큐 도입
- 웹 UI 고도화

