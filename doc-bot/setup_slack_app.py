#!/usr/bin/env python3
"""
Sandbox Doc Bot — 기존 앱 설정 자동화 (Socket Mode, Scopes, Install, Token 추출)
앱 ID: A0AN4L8E2B0
실행: python setup_slack_app.py
"""

import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

DOTENV_PATH = Path(__file__).parent / ".env"
APP_ID = "A0AN4L8E2B0"
TOKEN_LABEL = "doc-bot-socket"
BASE = f"https://api.slack.com/apps/{APP_ID}"

doc_bot_token = ""
doc_app_token = ""


async def ss(page, name):
    path = f"ss_{name}.png"
    await page.screenshot(path=path)
    print(f"      [screenshot] {path}")


async def main():
    global doc_bot_token, doc_app_token

    PROFILE_DIR = str(Path(__file__).parent / ".pw_profile")

    async with async_playwright() as p:
        # 지속 프로파일 — 로그인 세션 재사용
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            slow_mo=500,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # ── 로그인 확인 ────────────────────────────────────────────────────
        print(f"\n[0] 앱 페이지 접속: {BASE}")
        await page.goto(BASE, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # "Oh no!" 또는 로그인 페이지 감지
        page_text = await page.inner_text("body")
        needs_login = (
            "sign in" in page_text.lower()
            or "oh no" in page_text.lower()
            or "signin" in page.url
        )
        if needs_login:
            print("    ⚠ 로그인 필요 — 브라우저 창에서 api.slack.com에 로그인해주세요")
            print(f"    로그인 후 이 URL로 직접 이동: {BASE}")
            print("    (로그인 완료 시 자동으로 다음 단계 진행, 최대 10분 대기)")
            for i in range(120):
                await page.wait_for_timeout(5000)
                try:
                    txt = await page.inner_text("body")
                    if APP_ID in page.url and "oh no" not in txt.lower() and "sign in" not in txt.lower():
                        break
                except Exception:
                    pass
                if i % 6 == 0:
                    print(f"    대기 중... ({(i+1)*5}초 경과)")
            print("    ✓ 로그인 확인")

        # ── 1. Socket Mode 활성화 + App-Level Token ────────────────────────
        print("\n[1/5] Socket Mode 활성화...")
        await page.goto(f"{BASE}/socket-mode", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await ss(page, "1_socket_mode")

        # 토글 켜기 (Enable Socket Mode)
        try:
            toggle = await page.wait_for_selector(
                'input[type="checkbox"]', timeout=8000
            )
            if not await toggle.is_checked():
                await toggle.click()
                await page.wait_for_timeout(1500)
                print("    ✓ Socket Mode 토글 ON")
            else:
                print("    ✓ Socket Mode 이미 활성화")
        except PWTimeout:
            print("    ! 토글 없음 — 스킵")

        await ss(page, "2_socket_toggled")

        # "Generate an app-level token" 또는 "Add Token" 클릭
        try:
            gen_btn = await page.wait_for_selector(
                'button:has-text("Generate"), a:has-text("Generate"), '
                'button:has-text("Add Token"), a:has-text("Add Token")',
                timeout=8000,
            )
            await gen_btn.click()
            await page.wait_for_timeout(1200)
        except PWTimeout:
            print("    ! Generate 버튼 없음 — 이미 토큰 있거나 스킵")

        await ss(page, "3_generate_modal")

        # 토큰 이름 입력
        try:
            name_input = await page.wait_for_selector(
                'input[placeholder*="Token Name"], input[placeholder*="token"], '
                'input[id*="token"]',
                timeout=6000,
            )
            await name_input.fill(TOKEN_LABEL)
            await page.wait_for_timeout(400)
        except PWTimeout:
            print("    ! 토큰 이름 입력란 없음")

        # scope 추가
        try:
            scope_input = await page.wait_for_selector(
                'input[placeholder*="scope"], input[placeholder*="Search"]',
                timeout=5000,
            )
            await scope_input.fill("connections:write")
            await page.wait_for_timeout(700)
            await page.click(
                '[class*="option"]:has-text("connections:write"), '
                'li:has-text("connections:write")',
                timeout=5000,
            )
            await page.wait_for_timeout(400)
        except PWTimeout:
            # 이미 기본 선택됐을 수 있음
            pass

        # Generate 최종 클릭
        try:
            await page.click('button:has-text("Generate")', timeout=6000)
            await page.wait_for_timeout(2000)
        except PWTimeout:
            print("    ! Generate 버튼 없음")

        await ss(page, "4_token_generated")

        # xapp- 토큰 추출
        all_codes = await page.query_selector_all("code, [class*='token-value'], [class*='TokenDisplay']")
        for el in all_codes:
            try:
                txt = (await el.inner_text()).strip()
                if txt.startswith("xapp-"):
                    doc_app_token = txt
                    break
            except Exception:
                pass

        # 클립보드 시도
        if not doc_app_token:
            try:
                copy_btn = await page.wait_for_selector(
                    'button[title*="Copy"], button:has-text("Copy")', timeout=4000
                )
                await copy_btn.click()
                await page.wait_for_timeout(500)
                doc_app_token = await page.evaluate("navigator.clipboard.readText()")
                if not doc_app_token.startswith("xapp-"):
                    doc_app_token = ""
            except Exception:
                pass

        if doc_app_token:
            print(f"    ✓ App Token: {doc_app_token[:35]}...")
        else:
            print("    ⚠ App Token 자동 추출 실패 — 브라우저에서 확인 후 입력")
            await ss(page, "4b_token_manual")

        # Done 닫기
        try:
            await page.click('button:has-text("Done")', timeout=4000)
        except PWTimeout:
            pass

        # ── 2. Event Subscriptions ─────────────────────────────────────────
        print("\n[2/5] Event Subscriptions...")
        await page.goto(f"{BASE}/event-subscriptions", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        try:
            toggle = await page.wait_for_selector('input[type="checkbox"]', timeout=6000)
            if not await toggle.is_checked():
                await toggle.click()
                await page.wait_for_timeout(1200)
                print("    ✓ Events 토글 ON")
        except PWTimeout:
            pass

        try:
            add_btn = await page.wait_for_selector(
                'button:has-text("Add Bot User Event")', timeout=8000
            )
            await add_btn.click()
            await page.wait_for_timeout(500)
            search = await page.wait_for_selector(
                'input[type="search"], input[placeholder*="Search"]', timeout=6000
            )
            await search.fill("message.channels")
            await page.wait_for_timeout(800)
            await page.click(
                '[class*="option"]:has-text("message.channels"), div:has-text("message.channels")',
                timeout=5000,
            )
            await page.wait_for_timeout(500)
            print("    ✓ message.channels 추가")
        except PWTimeout:
            print("    ! message.channels 추가 실패 (수동 추가 필요)")

        try:
            await page.click('button:has-text("Save Changes")', timeout=5000)
            await page.wait_for_timeout(1000)
            print("    ✓ 저장")
        except PWTimeout:
            pass

        # ── 3. OAuth & Permissions — Scopes ───────────────────────────────
        print("\n[3/5] Bot Token Scopes...")
        await page.goto(f"{BASE}/oauth", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        for scope in ["chat:write", "files:write", "channels:history"]:
            try:
                add_scope_btn = await page.wait_for_selector(
                    'button:has-text("Add an OAuth Scope")', timeout=6000
                )
                await add_scope_btn.click()
                await page.wait_for_timeout(400)
                s = await page.wait_for_selector(
                    'input[placeholder*="Search"], input[type="search"]', timeout=5000
                )
                await s.fill(scope)
                await page.wait_for_timeout(700)
                await page.click(
                    f'[class*="option"]:has-text("{scope}"), div[role="option"]:has-text("{scope}")',
                    timeout=5000,
                )
                await page.wait_for_timeout(500)
                print(f"    + {scope}")
            except Exception as e:
                print(f"    ! {scope} 실패: {e}")

        await ss(page, "5_scopes")

        # ── 4. Install to Workspace ────────────────────────────────────────
        print("\n[4/5] 워크스페이스 설치...")
        await page.goto(f"{BASE}/install-on-team", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        try:
            install_btn = await page.wait_for_selector(
                'button:has-text("Install"), a:has-text("Install")', timeout=8000
            )
            await install_btn.click()
            await page.wait_for_timeout(2000)
            # OAuth Allow
            try:
                await page.click('button:has-text("Allow")', timeout=10000)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(2000)
                print("    ✓ 설치 완료")
            except PWTimeout:
                print("    ! Allow 버튼 없음 (이미 설치됐거나 수동 필요)")
        except PWTimeout:
            print("    ! Install 버튼 없음")

        await ss(page, "6_installed")

        # ── 5. Bot Token 추출 ──────────────────────────────────────────────
        print("\n[5/5] Bot Token 추출...")
        await page.goto(f"{BASE}/oauth", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await ss(page, "7_oauth_page")

        # xoxb- 토큰 직접 찾기
        all_els = await page.query_selector_all("code, input, [class*='token']")
        for el in all_els:
            try:
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                txt = ""
                if tag == "input":
                    txt = await el.get_attribute("value") or ""
                else:
                    txt = await el.inner_text()
                txt = txt.strip()
                if txt.startswith("xoxb-"):
                    doc_bot_token = txt
                    break
            except Exception:
                pass

        # Copy 버튼 클릭 → 클립보드
        if not doc_bot_token:
            try:
                copy_btns = await page.query_selector_all(
                    'button[title*="Copy"], button:has-text("Copy")'
                )
                for btn in copy_btns:
                    await btn.click()
                    await page.wait_for_timeout(500)
                    val = await page.evaluate("navigator.clipboard.readText()")
                    if val and val.startswith("xoxb-"):
                        doc_bot_token = val
                        print(f"    ✓ Bot Token (clipboard): {doc_bot_token[:35]}...")
                        break
            except Exception:
                pass

        if doc_bot_token:
            print(f"    ✓ Bot Token: {doc_bot_token[:35]}...")
        else:
            print("    ⚠ Bot Token 자동 추출 실패")
            print(f"    브라우저 OAuth 페이지: {BASE}/oauth")
            print("    xoxb- 토큰을 아래에 입력하세요 (혹은 Enter 스킵):")

        await ctx.close()

        # ── .env 업데이트 ──────────────────────────────────────────────────
        print("\n▶ .env 업데이트...")
        env_text = DOTENV_PATH.read_text(encoding="utf-8")

        updated = False
        if doc_bot_token:
            env_text = re.sub(r"DOC_BOT_TOKEN=.*", f"DOC_BOT_TOKEN={doc_bot_token}", env_text)
            updated = True
        if doc_app_token:
            env_text = re.sub(r"DOC_APP_TOKEN=.*", f"DOC_APP_TOKEN={doc_app_token}", env_text)
            updated = True

        if updated:
            DOTENV_PATH.write_text(env_text, encoding="utf-8")

        print("\n" + "=" * 60)
        print("결과:")
        print(f"  DOC_BOT_TOKEN: {doc_bot_token[:40] + '...' if doc_bot_token else '❌ 미추출'}")
        print(f"  DOC_APP_TOKEN: {doc_app_token[:40] + '...' if doc_app_token else '❌ 미추출'}")
        if updated:
            print("  ✅ .env 업데이트 완료")
        else:
            print("  ⚠ .env 미업데이트 — 토큰을 수동으로 .env에 입력하세요")
        print("\n다음 단계:")
        print("  1. Slack에서 /invite @Sandbox Doc Bot → 채널에 봇 초대")
        print("  2. 봇 재실행")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
