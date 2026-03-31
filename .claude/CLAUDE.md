# Sandbox Doc Bot — Claude Code 작업 가이드

Slack 샌드박스-문서자료실 채널에서 문서/서류 요청을 자동 감지하고
knowledge/files/ 의 실물 파일 또는 Notion 링크를 스레드로 전송하는 봇.
Claude API 없음 — 순수 키워드 매칭 방식.

---

## 가장 자주 하는 작업

### 1. alias 추가 / 수정
파일: `knowledge/documents.json`
```json
{
  "name": "사업자등록증",
  "aliases": ["사업자등록증", "사업자 등록증", "사업자증"],  ← 여기 추가
  "notion_url": "https://...",
  "local_file": "사업자등록증.pdf"
}
```
aliases 배열에 인식시킬 표현 추가 후 저장. 재시작 불필요.

### 2. 새 문서 추가
`knowledge/documents.json` 에 항목 추가 후
`python refresh_docs.py` 실행 → knowledge/files/ 에 파일 자동 저장.

### 3. 제외 키워드 수정
파일: `config.py` → EXCLUDE_KEYWORDS 리스트
봇이 응답하면 안 되는 키워드 (예: "인감" — 물리 도장 필요).

### 4. 봇 재시작 (로컬)
```
python main.py
```

---

## 파일별 역할

| 파일 | 역할 | 수정 빈도 |
|------|------|---------|
| knowledge/documents.json | 문서 목록·alias | 자주 |
| config.py | 채널 ID·제외 키워드 | 가끔 |
| agents/doc_request_agent.py | 감지·응답 로직 | 거의 안 함 |
| main.py | 봇 진입점 | 건드리지 않음 |
| refresh_docs.py | Notion→로컬 파일 동기화 | 실행만 함 |

---

## 환경변수 (.env)

```
DOC_BOT_TOKEN   — Slack 봇 토큰 (xoxb-...)
DOC_APP_TOKEN   — Slack 앱 토큰 (xapp-...)
NOTION_TOKEN    — Notion 통합 토큰
TEST_MODE       — true: 팀채널 미리보기 / false: 즉시 응답
```
.env.example 참고. 실제 값은 담당자에게 별도 수령.

---

## 수정 후 확인 방법

GA 팀 채널에서:
```
test: [요청 문구]
예: test: 사업자등록증 보내주세요
```
봇이 감지 결과를 스레드에 출력 (샌드박스-문서자료실 실제 전송 없음)

---

## 건드리면 안 되는 것
- main.py 소켓 연결 로직
- railway.toml (Railway 배포 설정)
- .gitignore (knowledge/files/ 제외 — 대용량 파일)
