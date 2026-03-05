# 뉴스레터 통합 수신 설계 (1차 Discord, 2차 Web)

- 작성일: 2026-03-05
- 범위: 개인 Discord 채널로 IT 뉴스 소스 상시 수신 + 이후 GitHub Pages 웹 아카이브
- 결정사항: GeekNews Slack 연동은 이번 범위에서 제외

## 1. 목표와 성공 기준

### 목표
- 여러 IT 뉴스 소스를 한 곳에서 관리하고, 새 소식을 개인 Discord로 자동 수신한다.
- 운영은 GitHub 중심으로 단순화한다(서버 상시 운영 없음).

### 성공 기준
- 수동 실행/스케줄 실행 모두 동작한다.
- 이미 보낸 항목은 다시 보내지 않는다.
- 일부 소스 장애가 있어도 전체 파이프라인은 계속 실행된다.
- 민감정보(Discord Webhook URL)가 저장소에 노출되지 않는다.

## 2. 접근 방식 비교

### A. GitHub Actions + Discord Webhook (채택)
- 장점: 무서버, 저비용, GitHub 기반 운영 단순
- 단점: RSS/Atom 등 공개 피드 중심으로 제약

### B. Zapier/Make 노코드 자동화
- 장점: 구축 매우 빠름
- 단점: 요금/할당량 제약, 워크플로우 가시성/이식성 낮음

### C. 전용 백엔드(FastAPI/Node)
- 장점: 확장성/커스터마이징 최고
- 단점: 초기 구축 및 운영 복잡도 높음

## 3. 아키텍처 (확정)

- `config/sources.yaml`: 수집 소스 목록 관리
- `scripts/fetch_and_send.py`: 피드 수집, 정규화, 중복 제거, Discord 전송
- `data/state.json`: 최근 전송 항목 식별자 저장
- `data/news.json`: 전송/아카이브용 정규화 데이터 저장 (2차 웹에서 사용)
- `.github/workflows/news-discord.yml`: 스케줄 실행 + 수동 실행

## 4. 데이터 흐름과 중복 제거 (확정)

1. `sources.yaml` 로드
2. 각 소스 피드 수집 (최신 N개)
3. 공통 포맷으로 정규화 (`source`, `title`, `link`, `published_at`, `id`)
4. 중복 제거
   - 1차: 링크 기준
   - 2차: `title + source` 해시
   - `state.json`에 최근 처리 ID 유지 (TTL/개수 제한)
5. 신규 항목만 Discord Webhook 전송
6. 실행 결과를 `last_run.json`에 기록

## 5. 장애 대응 / 운영 / 보안 (확정)

### 장애 대응
- 소스별 오류는 로그 기록 후 다음 소스로 진행(전체 중단 방지)
- Discord 전송 실패 시 재시도(백오프)

### 운영
- `schedule` + `workflow_dispatch` 지원
- 실행 결과(신규 개수/실패 개수/시간)를 로그와 파일로 남김

### 보안
- `DISCORD_WEBHOOK_URL`은 GitHub Secrets 사용
- 저장소에는 설정/상태만 저장, 비밀값 커밋 금지

## 6. 2차 웹 아카이브 설계 (확정)

- 데이터: `data/news.json`
- 배포: GitHub Pages
- 최소 기능: 최신순 목록, 소스 필터, 제목 검색, 원문 링크

## 7. 테스트 전략

- 단위 테스트: 정규화/중복 제거 로직
- 통합 테스트: 샘플 피드 입력 시 신규 항목 판별/상태 갱신 검증
- 운영 검증: Actions 수동 실행으로 Discord 수신 확인

## 8. 구현 단계

### 1차 (빠른 구축)
- 수집 스크립트 + Actions + 상태 저장 + Discord 전송

### 2차
- 정적 웹 아카이브(GitHub Pages)
- 필터/검색 UI 추가

## 9. 오픈 이슈

- 일부 뉴스레터는 RSS가 없을 수 있음(대체 수집 경로 필요)
- 과도한 메시지 발생 시 Discord 전송 묶음 정책 튜닝 필요
