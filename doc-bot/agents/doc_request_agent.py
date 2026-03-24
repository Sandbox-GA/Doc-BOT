# GA Automation Bot - 문서 요청 자동 안내 에이전트
# 새 문의 → 문서 키워드 감지 → 로컬 파일 Slack 업로드 or Notion 자료실 링크 안내
# Claude 호출 없음, 순수 키워드 매칭 (빠름)

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DOCUMENTS_PATH = Path(__file__).parent.parent / "knowledge" / "documents.json"
FILES_DIR = Path(__file__).parent.parent / "knowledge" / "files"

# ─── documents.json 캐시 (메시지마다 디스크 읽기 방지) ───────────────────────
_documents_cache: list = []
_cache_mtime: float = 0.0

# 문서 요청을 나타내는 동사/표현 (이 표현 + 문서 키워드 조합 시 감지)
REQUEST_VERBS = [
    "받", "주세요", "주실", "줄 수", "보내", "보내줘", "드릴", "드려",
    "구할", "얻을", "발급", "출력", "확인", "요청", "필요", "있나요",
    "있을까요", "있어요", "어디", "어떻게", "가능한가요", "가능할까요",
]

LIBRARY_URL = "https://www.notion.so/sandboxinc/30229436cbac81b8b88ef3bc1ab8fb7b"

# ─── 모호한 키워드 → 상세 입력 안내 ─────────────────────────────────────────
# 키: 정규화된 검색어 (소문자·공백 제거)
# hint: Slack에 보낼 안내 문구
AMBIGUOUS_KEYWORDS: dict[str, dict] = {
    "신고증": {
        "label": "신고증",
        "hint": (
            "예) 출판사 신고확인증, 영화 배급업 신고증, 영화 제작업 신고증,\n"
            "애니메이션 배급업 신고증, 통신판매업 신고증, 비디오물 제작업 신고증,\n"
            "방송영상독립제작사 신고증, 부가통신사업 신고증명서"
        ),
    },
    "영화": {
        "label": "영화",
        "hint": "예) 영화 배급업 신고증, 영화 제작업 신고증",
    },
    "애니메이션": {
        "label": "애니메이션",
        "hint": "예) 애니메이션 배급업 신고증, 애니메이션 제작업 신고증",
    },
    "애니": {
        "label": "애니메이션",
        "hint": "예) 애니메이션 배급업 신고증, 애니메이션 제작업 신고증",
    },
    "게임": {
        "label": "게임",
        "hint": "예) 게임배급업자 등록증, 게임제작업자 등록증",
    },
    "등록증": {
        "label": "등록증",
        "hint": "예) 게임배급업자 등록증, 게임제작업자 등록증, 대중문화예술기획업 등록증",
    },
}

# ─── 인사/비문서 패턴 — not_found 응답 제외 ──────────────────────────────────
_GREETING_PATTERNS = [
    "안녕", "감사", "고맙", "수고", "알겠", "확인했", "확인 했", "ok", "okay",
    "ㅋ", "ㅎ", "ㅠ", "ㅜ", "👍", "네네", "넵", "잠깐", "잠시",
]


def _is_greeting(text: str) -> bool:
    lower = text.lower().replace(" ", "")
    return any(g in lower for g in _GREETING_PATTERNS)


_aliases_cache: list = []  # [(normalized_alias, doc_index), ...] — 로드 시 사전 정규화


def _load_documents() -> list:
    """mtime 기반 캐시 — 파일이 변경됐을 때만 재읽기."""
    global _documents_cache, _cache_mtime, _aliases_cache
    if not DOCUMENTS_PATH.exists():
        return _documents_cache
    try:
        mtime = DOCUMENTS_PATH.stat().st_mtime
        if mtime != _cache_mtime:
            with open(DOCUMENTS_PATH, encoding="utf-8") as f:
                _documents_cache = json.load(f)
            _cache_mtime = mtime
            # 별칭 사전 정규화 (메시지마다 반복 처리 방지)
            _aliases_cache = [
                (alias.replace(" ", "").lower(), i)
                for i, doc in enumerate(_documents_cache)
                for alias in doc.get("aliases", [])
            ]
    except (OSError, json.JSONDecodeError):
        pass
    return _documents_cache


def detect_document_requests(text: str) -> list[dict]:
    """
    메시지에서 문서 요청 감지 (다중 반환).
    반환값: 매칭된 doc_info 리스트 (없으면 빈 리스트)
    """
    documents = _load_documents()
    lower_text = text.lower().replace(" ", "")
    matched = []
    matched_indices = set()

    # 1단계: 사전 정규화된 별칭으로 매칭 (별칭 재정규화 없음)
    for norm_alias, idx in _aliases_cache:
        if idx in matched_indices:
            continue
        if norm_alias in lower_text:
            doc = documents[idx]
            matched.append({
                "name": doc["name"],
                "notion_url": doc.get("notion_url", ""),
                "notion_url_2": doc.get("notion_url_2", ""),
                "description": doc.get("description", ""),
                "local_file": doc.get("local_file", ""),
                "is_group": doc.get("is_group", False),
            })
            matched_indices.add(idx)

    if matched:
        return matched

    # 2단계: 모호한 키워드 감지 → 상세 입력 요청
    for norm_key, info in AMBIGUOUS_KEYWORDS.items():
        if norm_key in lower_text:
            return [{
                "name": "모호한_키워드",
                "label": info["label"],
                "hint": info["hint"],
            }]

    # 3단계: 일반 문서/서류 요청인지 확인 (동사+문서명 조합)
    general_doc_keywords = [
        "서류", "자료", "문서", "증명서", "증빙", "첨부",
        "신청서", "계약서", "확인서", "등록증", "사본",
        "계산서", "영수증", "재직", "재무", "통장", "견적서",
    ]
    has_doc_keyword = any(kw in text for kw in general_doc_keywords)
    has_request_verb = any(verb in text for verb in REQUEST_VERBS)

    if has_doc_keyword and has_request_verb:
        return [{"name": "자료실_없음", "notion_url": LIBRARY_URL, "description": ""}]

    # 4단계: 짧은 단어 (≤ 20자) — 명시적 동사 없이 단어만 입력한 경우 → 없음 안내
    if len(text.replace(" ", "")) <= 20 and not _is_greeting(text):
        return [{"name": "없는_키워드", "query": text}]

    return []


def detect_document_request(text: str) -> dict | None:
    """단일 반환 호환용 — 첫 번째 결과만 반환."""
    results = detect_document_requests(text)
    return results[0] if results else None


VALID_DOC_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.hwp', '.zip'}


def has_local_file(doc_info: dict) -> bool:
    """로컬 캐시 파일이 존재하는지 확인. 인식 가능한 확장자만 허용."""
    local_file = doc_info.get("local_file")
    if not local_file:
        return False
    if Path(local_file).suffix.lower() not in VALID_DOC_EXTENSIONS:
        return False
    return (FILES_DIR / local_file).exists()


def upload_local_file(client, channel: str, thread_ts: str, doc_info: dict) -> bool:
    """
    로컬 캐시 파일을 Slack에 업로드.
    반환값: True(성공) / False(파일 없음 또는 실패)
    """
    local_file = doc_info.get("local_file")
    if not local_file:
        return False

    file_path = FILES_DIR / local_file
    if not file_path.exists():
        return False

    try:
        client.files_upload_v2(
            channel=channel,
            thread_ts=thread_ts,
            file=str(file_path),
            filename=local_file,
            title=doc_info["name"],
            initial_comment=f"📎 *{doc_info['name']}* 파일입니다.",
        )
        return True
    except Exception as e:
        logger.error(f"[upload_local_file] 파일 업로드 실패: {doc_info.get('name')}, {e}")
        return False


def build_reply(doc_info: dict, has_file: bool = False) -> str:
    """문서 안내 답변 텍스트 생성."""
    if doc_info["name"] == "모호한_키워드":
        label = doc_info.get("label", "서류")
        hint = doc_info.get("hint", "")
        return (
            f"*🤔 어떤 {label} 관련 서류가 필요하신가요?*\n\n"
            f"조금 더 상세히 입력해 주시면 바로 찾아드릴게요!\n\n"
            f"{hint}"
        )

    if doc_info["name"] == "없는_키워드":
        query = doc_info.get("query", "")
        return (
            f"*📭 '{query}' 관련 문서는 현재 자료실에 없습니다.*\n\n"
            f"👉 <{LIBRARY_URL}|🏠 샌드박스 문서 자료실>\n\n"
            f"📮 자료실에 없는 경우 GA팀에 문의해 주세요!"
        )

    if doc_info["name"] == "자료실_없음":
        return (
            f"*📭 요청하신 문서를 자료실에서 찾지 못했습니다.*\n\n"
            f"👉 <{doc_info['notion_url']}|🏠 샌드박스 문서 자료실>\n\n"
            f"📮 자료실에 없는 경우 GA팀에 문의해 주세요!"
        )

    if doc_info.get("is_group"):
        url1 = doc_info.get("notion_url", "")
        url2 = doc_info.get("notion_url_2", "")
        reply = "*📄 통장사본 요청이 확인되었습니다.*\n\n"
        reply += "원화/외화 중 필요하신 파일을 바로 보내드릴 수 있습니다.\n\n"
        if url1:
            reply += f"👉 <{url1}|📎 통장사본 (원화)>\n"
        if url2:
            reply += f"👉 <{url2}|📎 통장사본 (외화)>\n"
        reply += "\n원화인지 외화인지 알려주시면 파일을 바로 보내드립니다!"
        return reply

    desc = f" ({doc_info['description']})" if doc_info["description"] else ""
    notion_url = doc_info.get("notion_url", "")
    base = (
        f"*📄 {doc_info['name']}{desc} 요청이 확인되었습니다.*\n\n"
        f"아래 자료실에서 확인하실 수 있습니다.\n"
        f"👉 <{notion_url}|🏠 샌드박스 문서 자료실>\n\n"
    )
    if has_file:
        return base + "파일도 바로 아래에 첨부해 드립니다! 📎"
    return base.rstrip()
