# Sandbox Doc Bot - 설정 상수
# 문서 요청 감지 기능 전용. 사무 업무·주간 집계 기능 없음.

import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

# ─── 채널 ID ─────────────────────────────────────────────────────────────────────
DOC_CHANNEL = os.environ["HELPDESK_CHANNEL"]

# ─── 제외 키워드 (물리 인감 요청 → 봇 처리 불필요) ──────────────────────────────
EXCLUDE_KEYWORDS = ["인감증명", "인감 도장", "인감확인", "인감 신청", "인감 발급"]

# ─── 테스트 모드 ──────────────────────────────────────────────────────────────────
