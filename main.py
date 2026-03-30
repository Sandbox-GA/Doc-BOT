# Sandbox Doc Bot - 문서 요청 자동 안내 봇
#
# 역할: Slack 헬프데스크 채널에서 문서/서류 요청 키워드를 감지해
#       Notion 자료실 링크 또는 로컬 파일을 스레드로 바로 전송.
#
# Claude API 없음 — 순수 키워드 매칭으로 동작 (빠르고 가벼움)
#
# 실행: python main.py
# 사전 조건:
#   1. api.slack.com/apps 에서 Doc Bot 앱 생성
#   2. .env에 DOC_BOT_TOKEN, DOC_APP_TOKEN 입력
#   3. 헬프데스크 채널에 봇 초대: /invite @Sandbox Doc Bot
#   4. python refresh_docs.py 실행 → 로컬 파일 캐시 생성

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

from config import (
    HELPDESK_CHANNEL, TEAM_CHANNEL,
    WORK_START, WORK_END, KST,
    EXCLUDE_KEYWORDS, TEST_MODE,
)
import agents.doc_request_agent as doc_request

# ─── Slack Bolt 앱 초기화 ─────────────────────────────────────────────────────
app = App(token=os.environ["DOC_BOT_TOKEN"])

# ─── 중복 처리 방지 ───────────────────────────────────────────────────────────
_processed_ts: set[str] = set()


# ─── 유틸 함수 ────────────────────────────────────────────────────────────────
def is_work_hours() -> bool:
    now = datetime.now(KST)
    return WORK_START <= now.hour < WORK_END


def _is_excluded(text: str) -> bool:
    """인감 등 물리 대응 필수 문의 — 봇 처리 제외."""
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


# ─── 테스트 쿼리 공통 함수 ────────────────────────────────────────────────────
def _run_test_query(client, channel: str, ts: str, test_text: str, logger):
    """
    팀 채널에서 'test:' 입력 시 문서 요청 감지를 테스트.
    실제 헬프데스크 전송 없이 결과만 스레드로 확인 가능.
    """
    doc_info = doc_request.detect_document_request(test_text)
    if doc_info:
        reply_text = doc_request.build_reply(doc_info)
        client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text=f"*🧪 테스트 — 문서 요청 감지: {doc_info['name']}*\n\n{reply_text}",
        )
        # 로컬 캐시 파일이 있으면 파일 직접 업로드
        uploaded = doc_request.upload_local_file(client, channel, ts, doc_info)
        if not uploaded and not doc_request.has_local_file(doc_info):
            client.chat_postMessage(
                channel=channel,
                thread_ts=ts,
                text="_📌 파일 캐시 없음 — `python refresh_docs.py` 실행 후 파일 전송 가능_",
            )
    else:
        client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text="*🧪 테스트 결과*\n문서 요청이 감지되지 않았습니다.",
        )


# ─── 이벤트: 메시지 핸들러 ────────────────────────────────────────────────────
@app.event("message")
def handle_message(event, client, logger):
    channel = event.get("channel")

    # ── 팀 채널: 'test:' 입력 시 테스트 모드 ─────────────────────────────────
    if channel == TEAM_CHANNEL:
        if event.get("subtype") or event.get("bot_id"):
            return
        if event.get("thread_ts") and event.get("thread_ts") != event.get("ts"):
            return
        raw = event.get("text", "").strip()
        if not raw.lower().replace(" ", "").startswith("test:"):
            return
        test_text = raw[raw.lower().index(":") + 1:].strip()
        if not test_text:
            return
        logger.info(f"[test] 테스트 문의: {test_text}")
        _run_test_query(client, TEAM_CHANNEL, event.get("ts", ""), test_text, logger)
        return

    # ── 헬프데스크 채널만 이하 처리 ──────────────────────────────────────────
    if channel != HELPDESK_CHANNEL:
        return

    # 봇·시스템 메시지 제외
    if event.get("subtype") or event.get("bot_id"):
        return

    # 스레드 답변 제외 (신규 문의만)
    if event.get("thread_ts") and event.get("thread_ts") != event.get("ts"):
        return

    ts = event.get("ts", "")
    if ts in _processed_ts:
        return
    _processed_ts.add(ts)

    text = event.get("text", "").strip()
    if not text or len(text) < 5:
        return

    # 물리 대응 필수 문의 제외 (인감 등)
    if _is_excluded(text):
        logger.info(f"[filter] 제외 키워드 감지, 스킵: ts={ts}")
        return

    if not is_work_hours():
        return

    # ── 문서 요청 감지 ────────────────────────────────────────────────────────
    doc_info = doc_request.detect_document_request(text)
    if not doc_info:
        return  # 문서 요청이 아니면 무시

    reply_text = doc_request.build_reply(doc_info)
    has_file = doc_request.has_local_file(doc_info)
    file_status = (
        "📎 파일 캐시 있음 — 승인 시 Slack 파일 전송"
        if has_file
        else "🔗 파일 캐시 없음 — 링크만 안내 (`refresh_docs.py` 실행 필요)"
    )
    link = f"https://slack.com/archives/{HELPDESK_CHANNEL}/p{ts.replace('.', '')}"

    if TEST_MODE:
        # 테스트 모드: 팀 채널에 미리보기 카드 발송 → 담당자 승인 후 처리
        try:
            client.chat_postMessage(
                channel=TEAM_CHANNEL,
                text=f"📄 문서 요청 감지: {doc_info['name']}",
                blocks=[
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"📄 문서 요청 감지 — {doc_info['name']}"},
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*문의 내용:*\n{text[:300]}\n\n<{link}|원문 보기 →>"},
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"💡 *봇 제안 답변:*\n{reply_text}\n\n_{file_status}_"},
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "✅ 승인 (헬프데스크 답변)"},
                                "style": "primary",
                                "action_id": "doc_approve",
                                "value": json.dumps({
                                    "ts": ts,
                                    "reply": reply_text,
                                    "doc_name": doc_info["name"],
                                    "has_file": has_file,
                                    "local_file": doc_info.get("local_file", ""),
                                    "notion_url": doc_info.get("notion_url", ""),
                                    "description": doc_info.get("description", ""),
                                }),
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "❌ 건너뛰기"},
                                "style": "danger",
                                "action_id": "doc_skip",
                                "value": ts,
                            },
                        ],
                    },
                ],
            )
            logger.info(f"[doc_request][TEST] 문서 요청 카드 발송: {doc_info['name']}, ts={ts}")
        except Exception as e:
            logger.error(f"[doc_request] 카드 발송 실패: {e}")

    else:
        # 프로덕션 모드: 헬프데스크 스레드에 즉시 답변 + 파일 전송
        try:
            client.chat_postMessage(
                channel=HELPDESK_CHANNEL,
                thread_ts=ts,
                text=reply_text,
            )
            if has_file:
                doc_request.upload_local_file(client, HELPDESK_CHANNEL, ts, doc_info)
            logger.info(f"[doc_request][PROD] 즉시 답변 완료: {doc_info['name']}, ts={ts}")
        except Exception as e:
            logger.error(f"[doc_request] 즉시 답변 실패: {e}")


# ─── 버튼 액션: ✅ 승인 → 헬프데스크 답변 ───────────────────────────────────
@app.action("doc_approve")
def handle_doc_approve(ack, body, client, logger):
    ack()
    preview_ts = body["message"]["ts"]
    preview_channel = body["channel"]["id"]

    try:
        payload = json.loads(body["actions"][0]["value"])
    except (json.JSONDecodeError, KeyError):
        logger.error("[doc_approve] payload 파싱 실패")
        return

    helpdesk_ts = payload.get("ts", "")
    reply_text = payload.get("reply", "")
    has_file = payload.get("has_file", False)

    # 헬프데스크 스레드에 답변 발송
    try:
        client.chat_postMessage(
            channel=HELPDESK_CHANNEL,
            thread_ts=helpdesk_ts,
            text=reply_text,
        )
        # 파일 캐시 있으면 파일도 전송
        if has_file:
            doc_info = {
                "name": payload.get("doc_name", ""),
                "local_file": payload.get("local_file", ""),
                "notion_url": payload.get("notion_url", ""),
                "description": payload.get("description", ""),
            }
            doc_request.upload_local_file(client, HELPDESK_CHANNEL, helpdesk_ts, doc_info)

        # 팀 채널 카드 상태 업데이트
        client.chat_update(
            channel=preview_channel,
            ts=preview_ts,
            text="✅ *헬프데스크 답변 완료*",
            blocks=[{
                "type": "section",
                "text": {"type": "mrkdwn", "text": "✅ *헬프데스크 답변 완료*"},
            }],
        )
        logger.info(f"[doc_approve] 헬프데스크 답변 완료: ts={helpdesk_ts}")
    except Exception as e:
        logger.error(f"[doc_approve] 실패: {e}")


# ─── 버튼 액션: ❌ 건너뛰기 ──────────────────────────────────────────────────
@app.action("doc_skip")
def handle_doc_skip(ack, body, client, logger):
    ack()
    preview_ts = body["message"]["ts"]
    preview_channel = body["channel"]["id"]
    try:
        client.chat_update(
            channel=preview_channel,
            ts=preview_ts,
            text="❌ *이 문서 요청은 건너뛰었습니다.*",
            blocks=[{
                "type": "section",
                "text": {"type": "mrkdwn", "text": "❌ *이 문서 요청은 건너뛰었습니다.*"},
            }],
        )
    except Exception as e:
        logger.error(f"[doc_skip] 카드 업데이트 실패: {e}")


# ─── 진입점 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("Sandbox Doc Bot 시작")
    print(f"  헬프데스크 채널: {HELPDESK_CHANNEL}")
    print(f"  팀 채널: {TEAM_CHANNEL}")
    print("  기능: 문서 요청 키워드 감지 → Notion 링크 / 파일 전송")
    print(f"  모드: {'🧪 테스트 (팀 채널 승인 후 답변)' if TEST_MODE else '🚀 프로덕션 (헬프데스크 즉시 답변)'}")
    print("=" * 50)

    handler = SocketModeHandler(app, os.environ["DOC_APP_TOKEN"])
    handler.start()
