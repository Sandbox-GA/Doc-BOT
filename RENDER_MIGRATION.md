# Render 이관 가이드 (임시 — Railway 복구 전까지)

Railway 광범위 장애(2026-05-19~) 대응. Render free 플랜으로 임시 운영.

## 사용자 액션 (Render 대시보드)

1. https://dashboard.render.com 로그인
2. **New +** → **Blueprint** → `Sandbox-GA/Doc-BOT` (이 PR 머지 후 main)
3. `render.yaml` 자동 감지 → `sandbox-doc-bot` 서비스 1개
4. 환경변수 5개 입력 (UI에서 직접):

| 키 | 출처 |
|---|---|
| `DOC_BOT_TOKEN` | Slack 앱 → Bot User OAuth Token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Slack 앱 → Basic Information → Signing Secret |
| `NOTION_TOKEN` | Notion Integration Token (`secret_...`) |
| `HELPDESK_CHANNEL` | 운영 채널 ID |
| `TEAM_CHANNEL` | 팀 채널 ID |

값은 기존 Railway 대시보드 또는 로컬 `.env`에서 복사.

5. **Apply Blueprint** → 빌드 시작
6. 배포 URL(예: `https://sandbox-doc-bot.onrender.com`) 확보

## Slack 앱 Event URL 교체

- https://api.slack.com/apps → Doc Bot 앱 → **Event Subscriptions**
- Request URL: `https://sandbox-doc-bot.onrender.com/slack/events`

## Free 플랜 주의사항 (임시 운영이라 감수)

- 15분 idle 후 sleep → 첫 요청은 cold start (수 초 지연)
- Slack 이벤트가 잠든 사이 도착하면 누락 가능
- 월 750시간 무료
- Railway 복구되면 즉시 Railway로 복귀, 이 서비스는 일시정지/삭제

## Railway 복구 후 회수 절차

1. Railway 대시보드에서 Doc-BOT 서비스 재기동 확인
2. Slack Event URL을 Railway URL로 원복
3. Render 서비스 일시정지 또는 삭제
4. (선택) `render.yaml` 파일을 main에서 제거하는 PR
