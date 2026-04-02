# Sandbox Doc Bot — 마스터 가이드

## 봇이 하는 일
Slack 헬프데스크 채널에서 문서/서류 요청 메시지를 자동 감지하고,
Notion 자료실 링크 또는 로컬 파일을 스레드로 바로 전송.

- Claude API 없음 → 순수 키워드 매칭 (빠르고 저비용)
- TEST_MODE=true: 팀 채널에 확인 카드 발송 (확인 후 헬프데스크 전송)
- TEST_MODE=false: 헬프데스크 스레드에 즉시 자동 응답
- 스레드 내 메시지도 감지 (`@app.event("message")` 사용)

---

## 파일 구조

```
doc-bot/
├── main.py                      # 진입점 (Slack Bolt, HTTP 모드)
├── config.py                    # 설정 상수 (채널 ID, 근무시간, 제외 키워드)
├── requirements.txt             # 파이썬 패키지 목록
├── .env.example                 # 환경변수 예시 → .env로 복사 후 입력
├── refresh_docs.py              # Notion에서 파일 다운로드 → knowledge/files/ 저장
├── agents/
│   └── doc_request_agent.py    # 문서 요청 감지·응답 생성·파일 업로드 로직
└── knowledge/
    ├── documents.json           # 문서 목록 (이름, 키워드, Notion URL)
    └── files/                   # refresh_docs.py로 다운받은 로컬 파일 캐시
```

---

## .env 설정 — 필수 4개

```env
DOC_BOT_TOKEN=xoxb-xxxxxxxxxx
SLACK_SIGNING_SECRET=xxxxxxxxxx
NOTION_TOKEN=secret_xxxxxxxxxx
HELPDESK_CHANNEL=C03E08UCZS6
TEAM_CHANNEL=C08823F52U8
TEST_MODE=true
```

### 각 토큰 어디서 가져오나

| 키 | 위치 |
|----|------|
| `DOC_BOT_TOKEN` | api.slack.com/apps → 해당 앱 → OAuth & Permissions → Bot User OAuth Token |
| `SLACK_SIGNING_SECRET` | api.slack.com/apps → 해당 앱 → Basic Information → Signing Secret |
| `NOTION_TOKEN` | notion.so/profile/integrations → 해당 Integration → Internal Integration Secret |
| `TEST_MODE` | true (테스트), false (실제 운영) |

> **현재 토큰 위치**: 기존 PC의 `sandbox-doc-bot/.env` 또는 `ga-automation-bot/.env` 파일에서 복사

---

## Slack 앱 설정 요구사항

api.slack.com/apps에서 별도 앱 생성 필요 (GA 자동화봇과 분리)

### OAuth Scopes (Bot Token)
```
channels:history
groups:history
chat:write
files:write
```

### Event Subscriptions
- Request URL: `https://<Railway도메인>/slack/events`
- Subscribe: `message.channels`, `message.groups`

---

## 실행 방법

```bash
# 1. 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. .env 파일 생성
cp .env.example .env
# → .env 파일 열고 실제 토큰 값 입력

# 4. Notion 파일 다운로드 (선택, 파일 첨부 기능 사용 시)
python refresh_docs.py

# 5. 봇 실행
python main.py
```

---

## 테스트 방법

헬프데스크 채널에서:
```
test: 사업자등록증 보내주세요
```
→ 봇이 스레드에 감지 결과 출력 (헬프데스크에 전송)

---

## 문서 목록 설정 방법

`knowledge/documents.json` 에 직접 추가 (코딩 불필요, 메모장으로도 수정 가능):

```json
{
  "name": "재직증명서",
  "aliases": ["재직증명서", "재직 증명서", "재직확인"],
  "notion_url": "https://www.notion.so/...",
  "notion_page_id": "페이지ID",
  "local_file": "재직증명서.pdf",
  "local_files": ["재직증명서.pdf"],
  "description": "인사팀 발급"
}
```

추가 후 `python refresh_docs.py` 실행하면 파일이 자동 다운로드.

---

## 채널 ID 기본값
| 채널 | ID |
|------|----|
| 헬프데스크 | C03E08UCZS6 |
| GA 팀 채널 | C08823F52U8 |

변경 필요 시 .env에 `HELPDESK_CHANNEL`, `TEAM_CHANNEL` 수정.

---

## 배포 전 코드 리뷰 체크리스트

**코드를 push/배포하기 전 반드시 아래 항목 확인:**

### 1. 인코딩 깨짐 확인
- [ ] `main.py` — f-string 내 한글 깨짐 여부 (`?` 문자 확인)
- [ ] `config.py` — EXCLUDE_KEYWORDS 등 한글 값 정상 여부
- [ ] `agents/doc_request_agent.py` — 한글 상수/문자열 정상 여부
- [ ] f-string에서 따옴표 누락 (`SyntaxError: unterminated f-string`) 체크
- [ ] 주석 줄과 코드 줄이 같은 줄로 병합된 경우 없는지 확인 (특히 `#` 뒤에 실제 코드가 이어지는 경우)

### 2. Python 문법 오류
```bash
python -m py_compile main.py agents/doc_request_agent.py config.py
```
→ 오류 없이 통과해야 배포 가능

### 3. 핵심 기능 동작 확인
- [ ] `detect_document_requests("법인카드 보내주세요")` → 법인카드 문서 반환
- [ ] `has_local_file()`, `upload_local_file()` — `local_files` 리스트 필드 참조 정상
- [ ] EXCLUDE_KEYWORDS 필터 작동 ("인감증명" 입력 시 봇 응답 없어야 함)
- [ ] 스레드 메시지 감지 (`thread_ts` 있는 메시지도 처리)

### 4. 채널 알림 비활성화 확인
- [ ] `startup_check()` — Slack 메시지 전송 코드 없음
- [ ] `refresh_docs.py` — `notify_slack` 호출 비활성화 확인
- [ ] `handle_message()` — 봇 응답 외 채널 알림 없음

### 5. Railway 배포 후 확인
- [ ] Railway 로그에서 `SyntaxError`, `NameError`, `ImportError` 없음
- [ ] `startup_check` 출력에서 `✅ 토큰`, `✅ 스코프`, `✅ 채널` 확인
- [ ] 실제 테스트 메시지로 응답 확인

---

## 알려진 이슈 이력

| 날짜 | 증상 | 원인 | 해결 |
|------|------|------|------|
| 2026-03-26 | Railway Crashed (SyntaxError) | main.py 인코딩 깨짐으로 f-string 따옴표 누락 | main.py 전체 재작성 |
| 2026-03-26 | startup_check NameError: `r` | 주석+코드 줄 병합으로 `r = requests.post()` 주석 처리됨 | 줄 분리 복원 |
| 2026-03-26 | 인감 필터 동작 안 함 | config.py EXCLUDE_KEYWORDS 한글 깨짐 | config.py 재작성 |
| 2026-03-26 | 스레드 메시지 감지 안 됨 | `@app.message()` → `@app.event("message")` 변경 필요 | 핸들러 교체 |
