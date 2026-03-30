# GA Automation Bot - 문서 요청 자동 안내 에이전트
# 새 문의 → 문서 키워드 감지 → 로컬 파일 Slack 업로드 or Notion 자료실 링크 안내
# Claude 호출 없음, 순수 키워드 매칭 (빠름)

import json
from pathlib import Path

DOCUMENTS_PATH = Path(__file__).parent.parent / "knowledge" / "documents.json"
FILES_DIR = Path(__file__).parent.parent / "knowledge" / "files"

# 문서 요청을 나타내는 동사/표현 (이 표현 + 문서 키워드 조합 시 감지)
REQUEST_VERBS = [
    "받", "주세요", "주실", "줄 수", "보내", "보내줘", "드릴", "드려",
    "구할", "얻을", "발급", "출력", "확인", "요청", "필요", "있나요",
    "있을까요", "있어요", "어디", "어떻게", "가능한가요", "가능할까요",
]

LIBRARY_URL = "https://www.notion.so/sandboxinc/30229436cbac81b8b88ef3bc1ab8fb7b"


def _load_documents() -> list:
    if not DOCUMENTS_PATH.exists():
        return []
    try:
        with open(DOCUMENTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def detect_document_request(text: str) -> dict | None:
    """
    메시지에서 문서 요청 감지.
    반환값:
      - 특정 문서 매칭: {"name": ..., "notion_url": ..., "description": ...}
      - 문서 요청이지만 특정 문서 미매칭: {"name": "자료실", "notion_url": LIBRARY_URL, "description": ""}
      - 문서 요청 아님: None
    """
    documents = _load_documents()
    lower_text = text.lower().replace(" ", "")

    # 1단계: 특정 문서 키워드 매칭
    for doc in documents:
        for alias in doc["aliases"]:
            if alias.replace(" ", "").lower() in lower_text:
                return {
                    "name": doc["name"],
                    "notion_url": doc["notion_url"],
                    "description": doc["description"],
                    "local_file": doc.get("local_file", ""),
                }

    # 2단계: 일반 문서/서류 요청인지 확인
    general_doc_keywords = ["서류", "자료", "문서", "증명서", "증빙", "첨부"]
    has_doc_keyword = any(kw in text for kw in general_doc_keywords)
    has_request_verb = any(verb in text for verb in REQUEST_VERBS)

    if has_doc_keyword and has_request_verb:
        return {
            "name": "자료실",
            "notion_url": LIBRARY_URL,
            "description": "",
        }

    return None


def has_local_file(doc_info: dict) -> bool:
    """로컬 캐시 파일이 존재하는지 확인."""
    local_file = doc_info.get("local_file")
    if not local_file:
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
    except Exception:
        return False


def build_reply(doc_info: dict) -> str:
    """문서 안내 답변 텍스트 생성."""
    if doc_info["name"] == "자료실":
        return (
            f"*📂 문서/서류 요청이 확인되었습니다.*\n\n"
            f"샌드박스 공식 자료실에서 필요하신 문서를 찾아보실 수 있습니다.\n"
            f"👉 <{doc_info['notion_url']}|🏠 샌드박스 문서 자료실>\n\n"
            f"원하시는 문서가 없으면 GA팀에 직접 문의해 주세요!"
        )

    desc = f" ({doc_info['description']})" if doc_info["description"] else ""
    return (
        f"*📄 {doc_info['name']}{desc} 요청이 확인되었습니다.*\n\n"
        f"아래 자료실에서 확인하실 수 있습니다.\n"
        f"👉 <{doc_info['notion_url']}|🏠 샌드박스 문서 자료실>\n\n"
        f"해당 페이지에서 찾기 어려우시면 GA팀에 말씀해 주세요!"
    )
