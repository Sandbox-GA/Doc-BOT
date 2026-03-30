# Sandbox Doc Bot - 설정 상수
# 문서 요청 감지 전용 봇. 유사 사례·주간 통계 기능 없음.

import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

# ─── 채널 ID ─────────────────────────────────────────────────────────────────
HELPDESK_CHANNEL = os.environ.get("HELPDESK_CHANNEL", "C03E08UCZS6")
TEAM_CHANNEL = os.environ.get("TEAM_CHANNEL", "C08823F52U8")

# ─── 근무 시간 ─────────────────────────────────────────────────────────────────
WORK_START = 9
WORK_END = 19

# ─── 제외 키워드 (물리 대응 필수 → 봇 처리 불필요) ──────────────────────────
EXCLUDE_KEYWORDS = ["인감", "인감증명", "인감 도장", "인감날인", "인감 신청", "인감 발급"]

# ─── 테스트 모드 ──────────────────────────────────────────────────────────────
# True : 팀 채널에 미리보기 카드 발송 (승인 후 헬프데스크 답변)
# False: 헬프데스크에 즉시 답변
TEST_MODE = os.environ.get("TEST_MODE", "true").lower() == "true"
