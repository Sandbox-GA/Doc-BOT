# Claude Code로 Doc Bot 관리하기

팀원이 코드 없이 자연어로 봇을 관리할 수 있도록 Claude Code를 설치합니다.

---

## 1. 설치

**Node.js 설치 (처음 한 번만)**
https://nodejs.org → LTS 버전 다운로드 후 설치

**Claude Code 설치**
```bash
npm install -g @anthropic-ai/claude-code
```

**Claude 로그인**
```bash
claude
```
브라우저가 열리면 Anthropic 계정으로 로그인합니다. (계정 없으면 가입)

---

## 2. 저장소 클론

```bash
git clone https://github.com/taesup-ux/Sandbox-GA-Automation.git
cd Sandbox-GA-Automation/doc-bot
```

---

## 3. 사용법

프로젝트 폴더에서 Claude Code 실행:

```bash
claude
```

그 다음 아래 말만 입력하면 됩니다.

| 할 일 | 입력 |
|-------|------|
| Notion 새 문서 반영 | `리프레시 해줘` |
| 봇 상태 확인 | `봇 살아있어?` |
| 키워드 추가 | `사업자등록증 alias에 "사업자 등록" 추가해줘` |
| 동작 테스트 안내 | `테스트해줘` |

---

## 4. 리프레시 실행 예시

Notion 자료실에 새 문서를 추가한 후:

1. `claude` 실행
2. `리프레시 해줘` 입력
3. 완료 메시지 확인 → 봇 재시작 없이 바로 반영됨

---

## 문의

운영 중 문제가 생기면 Railway 로그 먼저 확인:
https://railway.com → 프로젝트 → Deployments → Logs
