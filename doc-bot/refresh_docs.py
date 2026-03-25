# Sandbox Doc Bot - Notion DB → documents.json + 파일 캐시 자동 동기화
#
# 동작:
#   1. Notion "자주찾는 공용 문서" DB + "자주찾는 부서별 문서" DB 전체 조회
#   2. documents.json에 없는 신규 문서 자동 추가 (aliases 자동 생성)
#   3. 기존 문서 파일 최신화 (Notion 파일명 → knowledge/files/ 저장)
#   4. documents.json 업데이트
#
# 실행: python refresh_docs.py

import json
import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_PATH = Path("knowledge/documents.json")
FILES_DIR = Path("knowledge/files")

# Notion DB IDs
PUBLIC_DB_ID = "30229436cbac8110874ae5443858295f"   # 자주찾는 공용 문서
DEPT_DB_ID   = "30229436cbac81fbaacce37d0dd6807d"   # 자주찾는 부서별 문서

NOTION_API = "https://api.notion.com/v1"
NOTION_VER = "2022-06-28"

# 지원하는 파일 확장자 (Notion에서 직접 다운로드 가능한 파일)
VALID_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.hwp', '.zip'}

# 문서명 앞 접두사 패턴 (제거 대상)
PREFIX_PATTERN = re.compile(r'^\s*(\[.*?\]\s*)+')


def notion_headers():
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise ValueError("❌ .env에 NOTION_TOKEN이 없습니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VER,
        "Content-Type": "application/json",
    }


def query_all_pages(db_id: str) -> list:
    """DB 전체 페이지 수집 (페이지네이션 자동 처리)."""
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(f"{NOTION_API}/databases/{db_id}/query",
                          headers=notion_headers(), json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return pages


def get_prop_text(props: dict, key: str) -> str:
    """title / rich_text 속성에서 텍스트 추출."""
    prop = props.get(key, {})
    items = prop.get("title") or prop.get("rich_text") or []
    return "".join(t.get("plain_text", "") for t in items).strip()


def get_file_info(props: dict) -> tuple[str, str]:
    """'문서 파일' 속성에서 (파일명, URL) 반환. 없으면 ('', '')."""
    files = props.get("문서 파일", {}).get("files", [])
    if not files:
        return "", ""
    f = files[0]
    name = f.get("name", "")
    if f["type"] == "file":
        url = f["file"]["url"]
    elif f["type"] == "external":
        url = f["external"]["url"]
    else:
        return "", ""
    return name, url


def get_url_prop(props: dict) -> str:
    """'URL' 속성에서 링크 추출."""
    return props.get("URL", {}).get("url") or ""


def strip_prefix(name: str) -> str:
    """[양식], [가이드], [필독], [공유] 등 접두사 제거."""
    return PREFIX_PATTERN.sub("", name).strip()


def make_aliases(name: str) -> list:
    """문서명으로 기본 aliases 자동 생성."""
    clean = strip_prefix(name)
    aliases = list(dict.fromkeys([name, clean] if clean != name else [name]))

    # 공백 없는 버전
    no_space = clean.replace(" ", "")
    if no_space not in aliases:
        aliases.append(no_space)

    # 괄호 제거
    no_bracket = re.sub(r"[()（）\[\]]", "", clean).strip()
    if no_bracket not in aliases:
        aliases.append(no_bracket)

    # 연도/분기 패턴 제거
    short = re.sub(r"\s*(20\d{2}|\d+Q|PPT/PDF|pdf|pptx)\s*", " ", clean, flags=re.IGNORECASE).strip()
    if short and short not in aliases:
        aliases.append(short)

    return list(dict.fromkeys(aliases))


def safe_filename(doc_name: str, notion_filename: str) -> str:
    """저장할 로컬 파일명 결정: 문서명 기반 + Notion 확장자."""
    ext = Path(notion_filename).suffix.lower() if notion_filename else ".pdf"
    if ext not in VALID_EXTENSIONS:
        ext = ".pdf"
    clean_name = strip_prefix(doc_name)
    base = re.sub(r'[\\/:*?"<>|]', "", clean_name)
    return base + ext


def download_file(url: str, save_path: Path) -> int:
    """파일 다운로드. 성공 시 파일 크기(KB) 반환."""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    save_path.write_bytes(r.content)
    return len(r.content) // 1024


def is_external_url(url: str) -> bool:
    """Google Drive / Google Docs / 외부 URL 여부 확인 (다운로드 불가)."""
    if not url:
        return False
    external_hosts = ["docs.google.com", "drive.google.com", "notion.so"]
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower()
    return any(h in host for h in external_hosts)


def sync_db(db_id: str, db_label: str, documents: list, existing_ids: dict) -> tuple[int, int, int, int]:
    """단일 DB 동기화. (added, updated, skipped, failed) 반환."""
    print(f"\n[{db_label}] 조회 중...")
    pages = query_all_pages(db_id)
    print(f"  {len(pages)}개 페이지 조회")

    added = updated = skipped = failed = 0

    for page in pages:
        page_id = page["id"].replace("-", "")
        props = page["properties"]
        notion_url = page.get("url", "")

        # 문서명 추출 (접두사 포함 원본 + 정제 버전 모두 사용)
        raw_name = get_prop_text(props, "문서명")
        if not raw_name:
            raw_name = get_prop_text(props, "페이지") or get_prop_text(props, "이름")
        if not raw_name:
            skipped += 1
            continue

        doc_name = strip_prefix(raw_name)  # 표시용 이름 (접두사 제거)

        notion_fname, file_url = get_file_info(props)

        # URL 속성 확인
        url_prop = get_url_prop(props)

        # 외부 URL → direct_url로 저장 (다운로드 불가)
        file_ext_url = ""
        if is_external_url(file_url) or is_external_url(notion_fname):
            file_ext_url = file_url or notion_fname
            file_url = ""
            notion_fname = ""

        # direct_url: URL 속성 우선, 없으면 파일의 외부 URL
        direct_url = url_prop or file_ext_url

        # 로컬 파일명 결정 (유효 확장자일 때만)
        local_file = ""
        if notion_fname and not is_external_url(notion_fname):
            ext = Path(notion_fname).suffix.lower()
            if ext in VALID_EXTENSIONS:
                local_file = safe_filename(doc_name, notion_fname)

        # 실물 파일 없으면 건너뜀 (가이드, URL 전용 등)
        if not local_file:
            print(f"  ⏭  {doc_name}: 실물 파일 없음 — 건너뜀")
            skipped += 1
            continue

        # ── 신규 문서 추가 ──────────────────────────────────────────
        if page_id not in existing_ids:
            new_doc = {
                "name": doc_name,
                "aliases": make_aliases(raw_name),
                "notion_url": notion_url,
                "notion_page_id": page_id,
                "local_file": local_file,
                "description": doc_name,
            }
            if direct_url:
                new_doc["direct_url"] = direct_url
            documents.append(new_doc)
            existing_ids[page_id] = len(documents) - 1
            print(f"  ➕ 신규: {doc_name}")
            added += 1
        else:
            idx = existing_ids[page_id]
            documents[idx]["notion_url"] = notion_url
            if local_file:
                documents[idx]["local_file"] = local_file
            if direct_url:
                documents[idx]["direct_url"] = direct_url

        # ── 파일 다운로드 ───────────────────────────────────────────
        if not file_url or not local_file:
            if not file_url:
                print(f"  ⏭  {doc_name}: 링크 전용")
            skipped += 1
            continue

        save_path = FILES_DIR / local_file
        try:
            size_kb = download_file(file_url, save_path)
            print(f"  ✅ {doc_name}: {local_file} ({size_kb}KB)")
            updated += 1
        except Exception as e:
            print(f"  ❌ {doc_name}: 다운로드 실패 — {e}")
            failed += 1

    return added, updated, skipped, failed


def main():
    FILES_DIR.mkdir(parents=True, exist_ok=True)

    # 기존 documents.json 로드
    if DOCUMENTS_PATH.exists():
        with open(DOCUMENTS_PATH, encoding="utf-8") as f:
            documents = json.load(f)
    else:
        documents = []

    # 실물 파일 없는 기존 항목 정리
    before = len(documents)
    documents = [d for d in documents if d.get("local_file")]
    existing_ids = {doc.get("notion_page_id", ""): i for i, doc in enumerate(documents)}
    if before != len(documents):
        print(f"[정리] URL 전용 기존 항목 {before - len(documents)}개 제거")

    print("=" * 55)
    print("Notion DB 동기화 시작")
    print("=" * 55)

    total_added = total_updated = total_skipped = total_failed = 0

    for db_id, label in [(PUBLIC_DB_ID, "공용 문서"), (DEPT_DB_ID, "부서별 문서")]:
        a, u, s, f = sync_db(db_id, label, documents, existing_ids)
        total_added += a
        total_updated += u
        total_skipped += s
        total_failed += f

    # documents.json 저장
    with open(DOCUMENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 55)
    print(f"✅ 완료: 신규 {total_added}개 | 파일 갱신 {total_updated}개 | 건너뜀 {total_skipped}개 | 실패 {total_failed}개")
    print(f"📝 documents.json 업데이트 완료 ({len(documents)}개 항목)")
    print("=" * 55)


if __name__ == "__main__":
    main()
