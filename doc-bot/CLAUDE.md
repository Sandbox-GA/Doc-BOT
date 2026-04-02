# Sandbox Doc Bot — Claude Code 작업 지침

이 프로젝트는 Slack 헬프데스크 채널의 문서 요청을 감지하고 실물 파일을 자동 전송하는 봇이다.
전체 구조와 배경은 TEAM_GUIDE.md를 먼저 읽는다.

---

## 자연어 명령 → 실행 매핑

아래 표현을 말하면 해당 작업을 바로 실행한다.

| 말하는 표현 | 실행 내용 |
|------------|-----------|
| "리프레시 해줘", "문서 업데이트", "노션 동기화" | `python refresh_docs.py` 실행 |
| "봇 상태 확인", "봇 살아있어?" | Railway 대시보드 URL 안내 + startup_check 로직 설명 |
| "테스트해줘", "동작 확인" | 테스트 메시지 형식 안내 (`test: 사업자등록증 보내주세요`) |
| "문서 추가해줘" | Notion 자료실 URL 안내 + 리프레시 절차 안내 |
| "alias 추가해줘" | documents.json 해당 항목의 aliases 배열에 추가 |

---

## 프로젝트 핵심 규칙

1. **코드 수정 전 반드시 읽기**: main.py, doc_request_agent.py, refresh_docs.py 순서로 파악
2. **환경변수는 .env 또는 Railway Variables에만**: 코드에 토큰 직접 입력 금지
3. **TEST_MODE=true 확인 후 수정**: 운영 채널에 오답변이 나가지 않도록
4. **refresh_docs.py는 봇 재시작 없이 실행 가능**: documents.json 갱신 후 즉시 반영됨

---

## 주요 파일 역할

```
main.py                  봇 진입점, startup_check() 포함
config.py                채널 ID 등 상수
refresh_docs.py          Notion → documents.json + files/ 동기화
agents/doc_request_agent.py  키워드 감지, 답변 생성, 파일 전송
knowledge/documents.json     등록된 문서 목록 (aliases 포함)
knowledge/files/             다운로드된 실물 파일
```

---

## Notion 자료실 정보

- 자료실: https://www.notion.so/sandboxinc/30229436cbac81b8b88ef3bc1ab8fb7b
- PUBLIC_DB_ID: `30229436cbac8110874ae5443858295f`
- DEPT_DB_ID: `30229436cbac81fbaacce37d0dd6807d`
- 실물 파일이 있는 항목만 추출 (가이드, URL 전용 제외)

---

## 배포

- 플랫폼: Railway (GitHub push → 자동 재배포)
- 운영 채널: C03E08UCZS6 (TEST_MODE=false)
- 테스트 채널: C0AMMQRNK1P (TEST_MODE=true)
