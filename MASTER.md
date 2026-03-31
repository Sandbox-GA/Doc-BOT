# Sandbox Doc Bot — 마스터 가이드

## 이 봇이 하는 일

Slack 샌드박스-문서자료실 채널에서 문서/서류 요청 메시지를 자동 감지하고,
Notion 자료실 링크 또는 로컬 파일을 스레드로 바로 전송.

- Claude API 없음 — 순수 키워드 매칭 (빠르고 저비용)
- TEST_MODE=true: 팀 채널에 승인 카드 발송 (담당자 승인 후 샌드박스-문서자료실 답변)
- TEST_MODE=false: 샌드박스-문서자료실 스레드에 즉시 자동 답변

---

## 파일 구조

```
sandbox-doc-bot/
├── main.py                      # 봇 진입점 (Slack Bolt, Socket Mode)
├── config.py                    # 설정 상수 (채널 ID, 근무시간, 제외 키워드)
├── requirements.txt             # 파이썬 패키지 목록
├── .env.example                 # 환경변수 예시 → .env로 복사 후 값 입력
├── refresh_docs.py              # Notion에서 파일 다운로드 → knowledge/files/ 저장
├── agents/
│   └── doc_request_agent.py    # 문서 요청 감지·답변 생성·파일 업로드 로직
└── knowledge/
    ├── documents.json           # 문서 목록 (이름, 키워드, Notion URL)
    └── files/                   # refresh_docs.py로 다운받은 로컬 파일 캐시
```

---

## .env 설정 — 필수 4개 값

```env
DOC_BOT_TOKEN=xoxb-xxxxxxxxxx
DOC_APP_TOKEN=xapp-xxxxxxxxxx
NOTION_TOKEN=secret_xxxxxxxxxx
TEST_MODE=true
```

### 각 값 어디서 가져오나?

| 값 | 위치 |
|----|------|
| `DOC_BOT_TOKEN` | api.slack.com/apps → 해당 앱 → OAuth & Permissions → Bot User OAuth Token |
| `DOC_APP_TOKEN` | api.slack.com/apps → 해당 앱 → Basic Information → App-Level Tokens |
| `NOTION_TOKEN` | notion.so/profile/integrations → 해당 Integration → Internal Integration Secret |
| `TEST_MODE` | true (테스트), false (실제 운영) |

> **현재 토큰 위치**: 기존 PC의 `sandbox-doc-bot/.env` 또는 `ga-automation-bot/.env` 파일에서 복사

---

## Slack 앱 설정 요구사항

api.slack.com/apps에서 별도 앱 생성 필요 (GA 자동화봇과 분리)

### OAuth Scopes (Bot Token)
```
channels:history
channels:read
chat:write
files:write
reactions:write
```

### Event Subscriptions
- Socket Mode 활성화 필수
- Subscribe: `message.channels`

### App-Level Token
- Scope: `connections:write`

---

## 실행 방법

```powershell
# 1. PowerShell 실행 정책 (새 Windows에서 최초 1회)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 2. 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate

# 3. 패키지 설치
pip install -r requirements.txt

# 4. .env 파일 생성
copy .env.example .env
# → .env 파일 열고 실제 토큰 값 입력

# 5. Notion 파일 다운로드 (선택, 파일 첨부 기능 사용 시)
python refresh_docs.py

# 6. 봇 실행
python main.py
```

---

## 테스트 방법

팀 채널에서:
```
test: 사업자등록증 보내주세요
```
→ 봇이 스레드에 감지 결과 출력 (샌드박스-문서자료실 전송 없음)

---

## 문서 목록 수정 방법

`knowledge/documents.json` 항목 추가 (코딩 불필요, 메모장으로 수정 가능):

```json
{
  "name": "재직증명서",
  "aliases": ["재직증명서", "재직 증명서", "재직확인서"],
  "notion_url": "https://www.notion.so/...",
  "notion_page_id": "페이지ID",
  "local_file": "재직증명서.pdf",
  "description": "인사팀 발급"
}
```

추가 후 `python refresh_docs.py` 실행하면 파일도 자동 다운로드.

---

## 채널 ID 기본값

| 채널 | ID |
|------|----|
| 샌드박스-문서자료실 | C03E08UCZS6 |
| GA 팀 채널 | C08823F52U8 |

변경 필요 시 .env에 `HELPDESK_CHANNEL`, `TEAM_CHANNEL` 추가.
