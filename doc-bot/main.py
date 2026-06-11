# Sandbox Doc Bot - 문서 요청 자동 안내 봇
#
# 목적: Slack 운영 채널(Acting Channel)에서 문서/서류 요청 키워드를 감지,
#       Notion 자료실 링크 또는 로컬 파일을 스레드로 바로 전송.
#
# Claude API 없음 → 순수 키워드 매칭으로 작동 (빠르고 가벼움)
#
# 실행: python main.py
# 전제 조건:
#   1. api.slack.com/apps 에서 Doc Bot 앱 생성
#   2. .env에 DOC_BOT_TOKEN, SLACK_SIGNING_SECRET 입력
#   3. 운영 채널(Acting Channel)에 봇 초대: /invite @Sandbox Doc Bot
#   4. python refresh_docs.py 실행 → 로컬 파일 캐시 생성 (선택)

import logging
import os
import re
import sys
import threading
from collections import OrderedDict

import requests
from dotenv import load_dotenv
from slack_bolt import App

logger = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

load_dotenv()

from config import (
    DOC_CHANNEL,
    EXCLUDE_KEYWORDS,
)
import agents.doc_request_agent as doc_request
import refresh_docs

# ─── 자료실 신규 문서 알림 트리거 ──────────────────────────────────────────────────
# Notion 자료실에 새 문서가 등록되면 알림이 떨어지는 채널.
# 이 채널에 메시지가 들어오면 refresh_docs.main() 을 백그라운드로 실행하고
# 신규 추가분이 있으면 운영 채널(NOTIFY_CHANNEL) 에 1줄 알림을 보낸다.
REFRESH_TRIGGER_CHANNEL = os.environ.get("REFRESH_TRIGGER_CHANNEL", "C0AUG33LBLJ")
NOTIFY_CHANNEL = os.environ.get("REFRESH_NOTIFY_CHANNEL", DOC_CHANNEL)
# 'test: <문구>' 입력 시 감지 결과만 미리보기(실제 자료실 전송 없음). 기본=알림채널.
TEST_CHANNEL = os.environ.get("TEST_CHANNEL", "C0AUG33LBLJ")
_refresh_lock = threading.Lock()
_refresh_running = False

# ─── Slack Bolt 앱 초기화 (HTTP 모드) ─────────────────────────────────────────────
app = App(
    token=os.environ["DOC_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)

# ─── 중복 처리 방지 (최근 1000건만 유지, O(1) 조회) ──────────────────────────────
_processed_ts: OrderedDict = OrderedDict()
_PROCESSED_MAX = 1000


# ─── 유틸 함수 ────────────────────────────────────────────────────────────────────
def _is_excluded(text: str) -> bool:
    """인감 등 물리 인감 요청 → 봇 처리 제외."""
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


# ─── 자료실 신규 문서 알림 → 자동 리프레시 ────────────────────────────────────────
def _run_refresh_and_notify(client) -> None:
    """refresh_docs.main() 을 실행하고 신규 추가분이 있으면 운영 채널에 알림."""
    global _refresh_running
    with _refresh_lock:
        if _refresh_running:
            logger.info("[refresh] 이미 진행 중 — 트리거 무시")
            return
        _refresh_running = True
    try:
        logger.info("[refresh] 자료실 알림 감지 → refresh_docs.main() 시작")
        result = refresh_docs.main()
        added = result.get("added", 0)
        updated = result.get("updated", 0)
        logger.info(
            f"[refresh] 완료: 신규 {added} / 파일 갱신 {updated} / "
            f"건너뜀 {result.get('skipped', 0)} / 실패 {result.get('failed', 0)} / "
            f"총 문서 {result.get('doc_count', 0)}"
        )
        if added > 0 or updated > 0:
            parts = []
            if added > 0:
                parts.append(f"신규 {added}건")
            if updated > 0:
                parts.append(f"갱신 {updated}건")
            summary = " / ".join(parts)
            try:
                client.chat_postMessage(
                    channel=NOTIFY_CHANNEL,
                    text=f"📚 자료실 업데이트: {summary}",
                )
            except Exception as e:
                logger.warning(f"[refresh] 알림 전송 실패: {e}")
    except Exception as e:
        logger.error(f"[refresh] 실행 실패: {e}", exc_info=True)
    finally:
        with _refresh_lock:
            _refresh_running = False


# ─── 이벤트: 메시지 핸들러 ─────────────────────────────────────────────────────────
@app.event("message")
def handle_message(event, client, logger):
    message = event
    subtype = event.get("subtype", "")
    channel = message.get("channel")

    # 테스트 프리뷰: 지정 채널에서 'test: <문구>' → 감지 결과만 미리보기(실제 전송 없음)
    # 'test:' 가 아닌 메시지는 아래 트리거/일반 로직으로 그대로 흘려보낸다.
    if TEST_CHANNEL and channel == TEST_CHANNEL:
        raw = (message.get("text") or "").strip()
        if not message.get("bot_id") and not subtype and raw.lower().replace(" ", "").startswith("test:"):
            query = raw.split(":", 1)[1].strip()
            ts = message.get("ts", "")
            if query:
                results = doc_request.detect_document_requests(query)
                if not results:
                    client.chat_postMessage(
                        channel=channel, thread_ts=ts,
                        text=f"🧪 *테스트* — '{query}': 감지된 문서 요청이 없습니다.")
                else:
                    for di in results:
                        hf = (not di.get("is_group")) and doc_request.has_local_file(di)
                        client.chat_postMessage(
                            channel=channel, thread_ts=ts,
                            text=f"🧪 *테스트 결과* — `{query}`\n\n{doc_request.build_reply(di, has_file=hf)}")
            return

    # 자료실 신규 문서 알림 채널 → bot_message 도 트리거로 사용 ────────────────────
    if channel == REFRESH_TRIGGER_CHANNEL:
        if subtype in ("message_deleted", "message_changed",
                       "channel_join", "channel_leave", "channel_topic"):
            return
        threading.Thread(
            target=_run_refresh_and_notify,
            args=(client,),
            daemon=True,
        ).start()
        return

    # 일반 채널은 삭제·수정·봇·시스템 subtype 제외 ──────────────────────────────────
    if subtype in ("message_deleted", "message_changed", "bot_message",
                   "channel_join", "channel_leave", "channel_topic"):
        return

    # 운영 채널(Acting Channel)만 이하 처리 ────────────────────────────────────────────────────
    if channel != DOC_CHANNEL:
        return

    # 봇·시스템 메시지 제외
    if message.get("bot_id"):
        return

    ts = message.get("ts", "")
    thread_ts = message.get("thread_ts") or ts

    if ts in _processed_ts:
        return
    _processed_ts[ts] = None
    if len(_processed_ts) > _PROCESSED_MAX:
        _processed_ts.popitem(last=False)

    text = message.get("text", "").strip()
    if not text or len(text) < 2:
        return

    if _is_excluded(text):
        logger.info(f"[filter] 제외 키워드 감지, 스킵: ts={ts}")
        return

    # 문서 요청 감지 (다중) ────────────────────────────────────────────────────────
    doc_list = doc_request.detect_document_requests(text)
    if not doc_list:
        return

    try:
        client.chat_postMessage(
            channel=DOC_CHANNEL,
            thread_ts=thread_ts,
            text="요청 수신했습니다! 서류 찾아드릴게요 🔍",
        )
    except Exception as e:
        logger.warning(f"[doc_request] 수신 확인 메시지 전송 실패 (계속 진행): {e}")

    for doc_info in doc_list:
        is_group = doc_info.get("is_group", False)
        has_file = False if is_group else doc_request.has_local_file(doc_info)
        can_download = not is_group and not has_file and doc_request.has_downloadable_url(doc_info)
        reply_text = doc_request.build_reply(doc_info, has_file=has_file)

        try:
            client.chat_postMessage(
                channel=DOC_CHANNEL,
                thread_ts=thread_ts,
                text=reply_text,
            )
            if has_file:
                doc_request.upload_local_file(client, DOC_CHANNEL, thread_ts, doc_info)
            elif can_download:
                doc_request.download_and_upload_url(client, DOC_CHANNEL, thread_ts, doc_info)
            logger.info(f"[doc_request] 응답 완료: {doc_info['name']}, ts={ts}")
        except Exception as e:
            logger.error(f"[doc_request] 실패: {e}")


# ─── 시작 상태 점검 ────────────────────────────────────────────────────────────────
def startup_check() -> bool:
    """앱 시작 전 필수 상태 점검. 실패 시 False 반환."""
    from pathlib import Path

    token = os.environ.get("DOC_BOT_TOKEN", "")
    h = {"Authorization": f"Bearer {token}"}
    ok = True

    print("━━━━ 상태 점검 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. 토큰 유효성
    r = requests.post("https://slack.com/api/auth.test", headers=h, timeout=10)
    d = r.json()
    if d.get("ok"):
        print(f"  ✅ 토큰  : {d.get('user')} / {d.get('team')}")
    else:
        print(f"  ❌ 토큰 오류: {d.get('error')}")
        ok = False

    # 2. 스코프 확인
    scopes = r.headers.get("X-OAuth-Scopes", "")
    required = {"chat:write", "files:write", "groups:history"}
    missing = required - set(s.strip() for s in scopes.split(","))
    if not missing:
        print(f"  ✅ 스코프: {scopes}")
    else:
        print(f"  ❌ 스코프 누락: {missing}")
        ok = False

    # 3. 채널 엑세스 가능 여부
    r2 = requests.post(
        "https://slack.com/api/conversations.info",
        headers=h,
        data={"channel": DOC_CHANNEL},
        timeout=10,
    )
    d2 = r2.json()
    if d2.get("ok") or d2.get("error") in ("missing_scope",):
        print(f"  ✅ 채널   : {DOC_CHANNEL}")
    elif d2.get("error") == "channel_not_found":
        print(f"  ❌ 채널 없음: {DOC_CHANNEL}")
        ok = False
    else:
        print(f"  ⚠️ 채널   : {DOC_CHANNEL} ({d2.get('error','ok')})")

    # 4. 로컬 파일 캐시 확인
    files_dir = Path(__file__).parent / "knowledge" / "files"
    file_count = len(list(files_dir.glob("*"))) if files_dir.exists() else 0
    doc_count = len(doc_request._load_documents())
    print("  docs: documents.json " + str(doc_count) + " / files " + str(file_count))

    # 5. Signing Secret 존재 확인
    if os.environ.get("SLACK_SIGNING_SECRET"):
        print("  Signing Secret: OK")
    else:
        print("  SLACK_SIGNING_SECRET: MISSING")
        ok = False

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if not ok:
        print("  ❌ 상태 점검 실패 — 위 항목 확인 후 재시작하세요")

    return ok


# ─── 진입점 ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))

    print("=" * 50)
    print("Sandbox Doc Bot 시작")
    print(f"  Acting Channel(운영): {DOC_CHANNEL}")
    print(f"  포트: {port}")
    print("  모드: HTTP / 키워드 감지 → 스레드 즉시 응답 + 파일 전송")
    print("=" * 50)

    if not startup_check():
        raise SystemExit(1)

    app.start(port=port)
