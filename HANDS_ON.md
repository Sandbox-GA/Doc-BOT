# Sandbox Doc Bot — 처음부터 직접 만들기 (실습 가이드)

**PPT 발표 이후 이 문서를 보고 직접 따라하세요.**
빈 폴더에서 시작해 클로드에게 말을 걸어 봇을 완성합니다.

**예상 소요 시간**: 약 90분
**준비물**: Windows PC, 인터넷 연결, Slack 워크스페이스 관리자 권한, Notion 계정

---

## 전체 순서

```
[설치]  1단계. Python 설치
        2단계. VS Code 설치
        3단계. Node.js 설치
        4단계. Claude Code 설치 + 로그인

[준비]  5단계. Slack 앱 만들기
        6단계. Notion 연동 설정

[제작]  7단계. 빈 폴더 만들고 Claude Code 실행
        8단계. 클로드에게 말 걸어서 봇 파일 만들기 (핵심!)

[실행]  9단계. 패키지 설치 + 봇 실행 + 테스트
```

---

## 1단계. Python 설치

Python = 컴퓨터가 실행할 수 있는 언어. 클로드가 짜준 코드를 실행하려면 필요합니다.

1. 브라우저에서 `python.org` 접속
2. 상단 **Downloads** → **Python 3.12.x** 클릭
3. 다운로드된 파일 실행
4. ⚠️ **반드시** 하단 **"Add Python to PATH"** 체크박스 체크
5. **Install Now** 클릭

**설치 확인**: 키보드 `Win + R` → `cmd` → Enter → 검은 창에 입력:
```
python --version
```
`Python 3.12.x` 가 나오면 성공.

---

## 2단계. VS Code 설치

VS Code = 코드를 보고 편집하는 프로그램. 터미널(명령어 입력창)이 내장되어 있습니다.

1. `code.visualstudio.com` 접속 → **Download for Windows**
2. 기본 설정으로 설치

**터미널 여는 방법**: VS Code 실행 후 상단 메뉴 **Terminal → New Terminal**
(또는 단축키 **Ctrl + `** — 백틱 키, 숫자 1 왼쪽)

> 터미널 = 마우스 없이 글자로 컴퓨터에 명령을 내리는 창.
> 이 문서에 나오는 명령어를 복사해서 붙여넣으면 됩니다.

---

## 3단계. Node.js 설치

Node.js = Claude Code를 설치하기 위해 필요한 부품입니다.

1. `nodejs.org` 접속 → **LTS** 버전 다운로드 (왼쪽 버튼)
2. 기본 설정으로 설치

**설치 확인** (VS Code 터미널에서):
```
node --version
```
`v20.x.x` 가 나오면 성공.

---

## 4단계. Claude Code 설치 + 로그인

Claude Code = AI 클로드와 대화하면서 코드를 짜게 시키는 도구.

**설치** (VS Code 터미널에서):
```
npm install -g @anthropic-ai/claude-code
```

**설치 확인**:
```
claude --version
```

**로그인**:
```
claude
```
브라우저가 열리면 Anthropic 계정으로 로그인.
계정 없으면 `claude.ai` 에서 회원가입 후 로그인.

---

## 5단계. Slack 앱 만들기

봇이 Slack에 접근하려면 전용 "앱"을 만들어야 합니다.

### 5-1. 앱 생성
1. `api.slack.com/apps` 접속 (Slack 계정 로그인)
2. **Create New App → From scratch**
3. App Name: `Sandbox Doc Bot` / 워크스페이스 선택 → **Create App**

### 5-2. Socket Mode 활성화
1. 왼쪽 메뉴 **Settings → Socket Mode → Enable**
2. Token Name: `doc-bot-app-token` → **Generate**
3. `xapp-` 로 시작하는 토큰 → **복사해서 메모장에 저장** ⭐

### 5-3. 권한 설정
1. 왼쪽 메뉴 **OAuth & Permissions → Bot Token Scopes**
2. **Add an OAuth Scope** 클릭, 아래 항목 하나씩 추가:
   - `channels:read`
   - `chat:write`
   - `chat:write.customize`
   - `files:write`
   - `reactions:read`
   - `reactions:write`

### 5-4. Bot Token 발급
1. **OAuth & Permissions** 상단 **Install to Workspace → Allow**
2. `xoxb-` 로 시작하는 **Bot User OAuth Token** → **복사해서 메모장에 저장** ⭐

### 5-5. 이벤트 구독
1. 왼쪽 메뉴 **Event Subscriptions → Enable Events 켜기**
2. **Subscribe to bot events** → **Add Bot User Event**:
   - `message.channels`
   - `message.groups`
   - `reaction_added`
3. **Save Changes**

### 5-6. 채널에 봇 초대 (Slack 앱에서)
```
/invite @Sandbox Doc Bot
```
샌드박스-문서자료실 채널, GA 팀 채널 두 곳 모두.

---

## 6단계. Notion 연동 설정

### 6-1. Integration 생성
1. `notion.so/my-integrations` 접속 → **+ New integration**
2. Name: `Sandbox Doc Bot` → **Submit**
3. **Internal Integration Secret** (`secret_` 로 시작) → **복사해서 메모장에 저장** ⭐

### 6-2. 자료실 페이지 연결
1. Notion 자료실 페이지 열기
2. 오른쪽 상단 **...** → **Connections → Sandbox Doc Bot** 선택
3. 자료실 안 문서 페이지들도 동일하게 연결

---

## 7단계. 빈 폴더 만들고 Claude Code 실행

이제 본격적으로 봇을 만들 차례입니다.

### 7-1. 프로젝트 폴더 만들기

VS Code 터미널에서:
```
mkdir C:\Users\$env:USERNAME\my-doc-bot
cd C:\Users\$env:USERNAME\my-doc-bot
```

> `$env:USERNAME` 은 현재 PC 사용자 이름으로 자동 변환됩니다.
> 예: `C:\Users\taesup\my-doc-bot`

### 7-2. VS Code에서 폴더 열기

**File → Open Folder** → 방금 만든 `my-doc-bot` 폴더 선택

### 7-3. Claude Code 실행

VS Code 터미널에서:
```
claude
```

> 이제 클로드와 대화할 수 있습니다.
> 아래 8단계의 프롬프트를 순서대로 입력하세요.

---

## 8단계. 클로드에게 말 걸어서 봇 만들기 ⭐ 핵심

> 아래 프롬프트를 **순서대로** 클로드에게 입력하세요.
> 클로드가 파일을 만들고 나면 다음 프롬프트를 입력합니다.

---

### 프롬프트 1 — 프로젝트 방향 설명

```
Slack 샌드박스-문서자료실 채널에서 문서 요청 키워드를 감지해서
Notion 자료실 링크나 파일을 자동으로 보내주는 봇을 만들 거야.

파이썬, Slack Bolt (Socket Mode), Notion API를 쓸 거고
Claude API는 사용하지 않아. 순수 키워드 매칭으로만 동작해.

먼저 어떤 파일들이 필요한지 구조만 잡아줘. 코드는 아직 짜지 말고.
```

> 클로드가 파일 구조를 제안합니다. 확인 후 다음 진행.

---

### 프롬프트 2 — 문서 목록 파일 만들기

```
knowledge/documents.json 파일 만들어줘.

각 문서 항목에는 아래 정보가 들어가야 해:
- name: 문서 이름
- aliases: 이 문서를 요청할 때 쓸 수 있는 다양한 표현 목록
- notion_url: Notion 자료실 해당 페이지 URL
- notion_page_id: Notion 페이지 ID (나중에 파일 다운로드용)
- local_file: 로컬에 저장할 파일명
- description: 한 줄 설명

예시 문서 2개만 넣어줘: 사업자등록증, 회사소개서
```

> 파일이 생성되면 내용 확인. aliases(키워드)가 충분한지 체크.

---

### 프롬프트 3 — 설정 파일 만들기

```
config.py 만들어줘.

포함할 내용:
- HELPDESK_CHANNEL: Slack 샌드박스-문서자료실 채널 ID (환경변수에서 읽기)
- TEAM_CHANNEL: GA 팀 채널 ID (환경변수에서 읽기)
- 근무시간: 9시~19시 (KST)
- EXCLUDE_KEYWORDS: 인감, 인감증명, 인감 도장, 인감날인 (물리 대응 필요해서 봇 제외)
- TEST_MODE: 환경변수에서 읽기, 기본값 true
```

---

### 프롬프트 4 — 문서 감지 + 파일 전송 로직 만들기

```
agents/doc_request_agent.py 만들어줘.

기능:
1. detect_document_request(text): 텍스트에서 문서 요청 감지
   - documents.json 읽어서 aliases 키워드 매칭
   - 특정 문서 못 찾으면 일반 서류 요청인지 확인 (서류/자료/문서 + 요청 동사 조합)
   - 감지되면 문서 정보 dict 반환, 아니면 None

2. has_local_file(doc_info): 로컬 캐시 파일 존재 여부 확인

3. upload_local_file(client, channel, thread_ts, doc_info): Slack에 파일 업로드

4. build_reply(doc_info): 답변 텍스트 생성
```

> 핵심 로직입니다. 완성되면 클로드에게 테스트 방법도 물어보세요:
> "이 함수 터미널에서 바로 테스트해볼 수 있어?"

---

### 프롬프트 5 — 메인 봇 만들기

```
main.py 만들어줘. Slack Bolt Socket Mode 기반.

동작 방식:
- 샌드박스-문서자료실 채널 새 메시지 → doc_request_agent로 문서 요청 감지
- TEST_MODE=true: 팀 채널에 미리보기 카드 발송 (승인/건너뛰기 버튼 포함)
- TEST_MODE=false: 샌드박스-문서자료실 스레드에 즉시 답변 + 파일 첨부

필터:
- 근무시간 외 메시지 무시
- 인감 관련 키워드 무시 (EXCLUDE_KEYWORDS)
- 봇 메시지, 스레드 답변 무시

테스트 편의 기능:
- 팀 채널에서 "test: [문의내용]" 입력하면 결과 스레드로 확인 가능

환경변수에서 DOC_BOT_TOKEN, DOC_APP_TOKEN 읽기
```

---

### 프롬프트 6 — Notion 파일 다운로드 스크립트

```
refresh_docs.py 만들어줘.

동작:
- documents.json 읽어서 notion_page_id 있는 문서마다
- Notion API로 "문서 파일" 속성의 파일 URL 가져와서
- knowledge/files/ 폴더에 저장
- 저장 후 documents.json의 local_file 필드 업데이트

환경변수에서 NOTION_TOKEN 읽기
```

---

### 프롬프트 7 — 패키지 목록 + 환경변수 예시 파일

```
마지막으로 두 가지 만들어줘.

1. requirements.txt
   필요한 패키지: slack-bolt, slack-sdk, python-dotenv, requests, notion-client

2. .env.example
   필요한 환경변수 목록과 설명 주석 포함:
   - DOC_BOT_TOKEN (Slack Bot Token, xoxb-로 시작)
   - DOC_APP_TOKEN (Slack App Token, xapp-로 시작)
   - HELPDESK_CHANNEL (샌드박스-문서자료실 채널 ID)
   - TEAM_CHANNEL (팀 채널 ID)
   - NOTION_TOKEN (Notion Integration Secret)
   - TEST_MODE (true/false)
```

---

## 9단계. 패키지 설치 + .env 설정 + 봇 실행

### 9-1. PowerShell 스크립트 실행 허용 (새 컴퓨터 필수)

Windows 새 노트북은 기본적으로 스크립트 실행을 막습니다.
VS Code 터미널에서 아래 명령어를 **한 번만** 실행:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

`Y` 입력 후 Enter.

### 9-2. 가상환경 만들기 (VS Code 터미널에서)

```
python -m venv .venv
```
```
.venv\Scripts\activate
```
터미널 앞에 `(.venv)` 가 붙으면 성공.

```
pip install -r requirements.txt
```
1~2분 소요.

### 9-2. .env 파일 만들기

```
copy .env.example .env
```

`.env` 파일 열어서 5단계, 6단계에서 메모장에 저장해둔 토큰 입력 후 **Ctrl+S** 저장.

```
DOC_BOT_TOKEN=xoxb-여기에_붙여넣기
DOC_APP_TOKEN=xapp-여기에_붙여넣기
HELPDESK_CHANNEL=C03E08UCZS6
TEAM_CHANNEL=C08823F52U8
NOTION_TOKEN=secret_여기에_붙여넣기
TEST_MODE=true
```

⚠️ .env 파일은 절대 공유하지 마세요.

### 9-3. Notion 파일 다운로드

```
python refresh_docs.py
```
`✅ 사업자등록증 저장 완료` 메시지가 나오면 성공.

### 9-4. 봇 실행

```
python main.py
```
`Sandbox Doc Bot 시작` 메시지가 나오면 성공.

### 9-5. 테스트

Slack GA 팀 채널에서 입력:
```
test: 사업자등록증 받을 수 있을까요?
```
봇이 스레드에 카드를 보내면 완성! 🎉

---

## 문제가 생겼을 때

| 증상 | 해결 |
|------|------|
| `python` 명령어가 안 먹힘 | Python 재설치 → "Add to PATH" 체크 확인 |
| `(.venv)` 가 안 붙음 | `.venv\Scripts\activate` 다시 실행 |
| `ModuleNotFoundError` | `pip install -r requirements.txt` 재실행 |
| `Invalid token` 오류 | `.env` 파일 토큰 값 오타 확인 |
| 봇이 메시지를 안 받음 | `/invite @Sandbox Doc Bot` 채널 초대 확인 |
| Notion 파일 없음 | `documents.json`에 `notion_page_id` 입력 후 `refresh_docs.py` 재실행 |

---

## 다음에 다시 실행할 때

```
cd C:\Users\$env:USERNAME\my-doc-bot
.venv\Scripts\activate
python main.py
```
