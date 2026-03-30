# GA Automation Bot - Notion 문서 파일 로컬 캐시 갱신
# 실행: python refresh_docs.py
#
# 동작:
#   documents.json의 각 문서 → Notion 페이지에서 파일 다운로드 → knowledge/files/ 저장
#   파일이 업데이트된 경우 덮어씀

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

DOCUMENTS_PATH = Path("knowledge/documents.json")
FILES_DIR = Path("knowledge/files")


def main():
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("❌ .env에 NOTION_TOKEN이 없습니다.")
        return

    notion = Client(auth=token)

    with open(DOCUMENTS_PATH, encoding="utf-8") as f:
        documents = json.load(f)

    FILES_DIR.mkdir(parents=True, exist_ok=True)

    success, skipped, failed = 0, 0, 0

    for doc in documents:
        name = doc["name"]
        page_id = doc.get("notion_page_id", "").strip()

        if not page_id:
            print(f"⏭  {name}: notion_page_id 미입력, 건너뜀")
            skipped += 1
            continue

        try:
            page = notion.pages.retrieve(page_id=page_id)
            props = page.get("properties", {})

            # "문서 파일" 속성에서 파일 URL 추출 (Files & media 타입)
            file_prop = props.get("문서 파일", {})
            files = file_prop.get("files", [])

            if not files:
                print(f"⚠️  {name}: Notion 페이지에 첨부 파일 없음")
                skipped += 1
                continue

            file_info = files[0]
            if file_info["type"] == "file":
                file_url = file_info["file"]["url"]
            elif file_info["type"] == "external":
                file_url = file_info["external"]["url"]
            else:
                print(f"⚠️  {name}: 알 수 없는 파일 타입 ({file_info['type']})")
                skipped += 1
                continue

            # Notion 실제 파일명 사용 (확장자 보존)
            notion_filename = file_info.get("name", "")
            if notion_filename:
                # 확장자 추출해서 local_file에 적용
                ext = Path(notion_filename).suffix  # .pdf / .pptx / .docx 등
                base = Path(doc.get("local_file") or name).stem
                filename = base + ext
            else:
                filename = doc.get("local_file") or f"{name}.pdf"

            save_path = FILES_DIR / filename

            resp = requests.get(file_url, timeout=60)
            resp.raise_for_status()

            save_path.write_bytes(resp.content)
            size_kb = len(resp.content) // 1024

            # documents.json의 local_file 업데이트 (확장자 변경 반영)
            doc["local_file"] = filename

            print(f"✅ {name}: {filename} 저장 완료 ({size_kb}KB)")
            success += 1

        except Exception as e:
            print(f"❌ {name}: 오류 — {e}")
            failed += 1

    # local_file 변경사항 documents.json에 저장
    if success > 0:
        with open(DOCUMENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        print("📝 documents.json 업데이트 완료 (local_file 확장자 반영)")

    print()
    print(f"완료: 성공 {success}개 | 건너뜀 {skipped}개 | 실패 {failed}개")
    if success > 0:
        print("이후 문서 요청 시 로컬 파일이 Slack으로 바로 전송됩니다.")


if __name__ == "__main__":
    main()
