#!/usr/bin/env python3
"""
Sandbox Doc Bot — Slack 앱 자동 생성 + 토큰 발급
실행: python create_slack_app.py
"""

import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

DOTENV_PATH = Path(__file__).parent / ".env"
APP_NAME = "Sandbox Doc Bot"
TOKEN_LABEL = "doc-bot-socket"

doc_bot_token = ""
doc_app_token = ""


async def wait_click(page, selector, timeout=10000):
    el = await page.wait_for_selector(selector, timeout=timeout)
    await el.scroll_into_view_if_needed()
    await el.click()
    await page.wait_for_timeout(800)


async def main():
    global doc_bot_token, doc_app_token

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=400,
            args=["--start-maximized"],
        )
        ctx = await browser.new_context(no_viewport=True)
        page = await ctx.new_page()

        # ── 1. api.slack.com/apps ──────────────────────────────────────────
        print("\n[1/7] api.slack.com/apps 접속...")
        await page.goto("https://api.slack.com/apps", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        if "api.slack.com/apps" not in page.url:
            print("      ⚠ 로그인 필요 — 브라우저에서 Slack에 로그인해주세요 (최대 3분)")
            try:
                await page.wait_for_url("https://api.slack.com/apps**", timeout=180000)
                print("      ✓ 로그인 완료")
            except PWTimeout:
                print("      ✗ 타임아웃 — 종료")
                return

        await page.wait_for_timeout(2000)

        # 로그인 필요 여부 체크 (URL은 api.slack.com/apps 이지만 비로그인 상태일 수 있음)
        sign_in_link = await page.query_selector('a:has-text("sign in")')
        if sign_in_link:
            print("      ⚠ 로그인 필요 — 지금 열린 브라우저 창에서 Slack API에 로그인해주세요!")
            await sign_in_link.click()
            await page.wait_for_timeout(1500)

            # 폴링: 5초마다 로그인 여부 확인 (최대 10분)
            logged_in = False
            for i in range(120):
                await page.wait_for_timeout(5000)
                url = page.url
                # api.slack.com 으로 돌아왔고 로그인 페이지가 아닌 경우
                if "api.slack.com" in url and "signin" not in url and "login" not in url:
                    # Create New App 버튼 있으면 진짜 로그인 완료
                    create_btn = await page.query_selector(
                        'a:has-text("Create New App"), button:has-text("Create New App")'
                    )
                    if create_btn:
                        logged_in = True
                        break
                    # apps 페이지로 명시 이동
                    await page.goto("https://api.slack.com/apps", wait_until="domcontentloaded")
                    await page.wait_for_timeout(1500)
                    create_btn = await page.query_selector(
                        'a:has-text("Create New App"), button:has-text("Create New App")'
                    )
                    if create_btn:
                        logged_in = True
                        break
                if i % 6 == 0:
                    print(f"      대기 중... ({(i+1)*5}초 경과) — 브라우저 창을 확인해주세요")

            if not logged_in:
                print("      ✗ 로그인 타임아웃 (10분). 다시 실행해주세요")
                await browser.close()
                return

            print("      ✓ 로그인 완료")
            await page.wait_for_timeout(1500)

        # ── 2. Create New App ──────────────────────────────────────────────
        print("[2/7] 새 앱 생성...")
        try:
            await wait_click(page, 'a:has-text("Create New App"), button:has-text("Create New App")')
        except PWTimeout:
            await wait_click(page, 'text="Create New App"')

        await page.wait_for_timeout(1200)

        # From scratch 선택
        try:
            await wait_click(page, 'text="From scratch"', timeout=8000)
        except PWTimeout:
            pass  # 바로 폼으로 넘어갈 수도 있음

        await page.wait_for_timeout(800)

        # 앱 이름 입력
        name_input = await page.wait_for_selector(
            'input[id="app-config-name"], input[placeholder*="app"], input[placeholder*="name"]',
            timeout=10000,
        )
        await name_input.triple_click()
        await name_input.fill(APP_NAME)
        await page.wait_for_timeout(500)

        # 워크스페이스 드롭다운 — 첫 번째 옵션 선택
        try:
            ws_select = await page.query_selector('select[name*="team"], select[id*="team"]')
            if ws_select:
                options = await ws_select.query_selector_all("option")
                for opt in options:
                    val = await opt.get_attribute("value")
                    if val and val.strip():
                        await ws_select.select_option(value=val)
                        break
        except Exception as e:
            print(f"      (워크스페이스 선택 스킵: {e})")

        await page.wait_for_timeout(500)

        # Create App 클릭
        await wait_click(page, 'button:has-text("Create App")', timeout=10000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 앱 ID 추출
        app_id_match = re.search(r"/apps/([A-Z0-9]+)", page.url)
        app_id = app_id_match.group(1) if app_id_match else None
        print(f"      ✓ 앱 생성 완료  (app_id={app_id})")

        if not app_id:
            print("      ✗ app_id를 추출할 수 없습니다. URL 확인 필요")
            input("      계속하려면 Enter...")
            app_id_match = re.search(r"/apps/([A-Z0-9]+)", page.url)
            app_id = app_id_match.group(1) if app_id_match else None

        # ── 3. Socket Mode + App-Level Token ──────────────────────────────
        print("[3/7] Socket Mode 활성화 + App-Level Token 발급...")
        await page.goto(
            f"https://api.slack.com/apps/{app_id}/socket-mode",
            wait_until="networkidle",
        )
        await page.wait_for_timeout(1500)

        # 토글 켜기
        try:
            toggle = await page.query_selector(
                'input[type="checkbox"][id*="socket"], input[type="checkbox"]'
            )
            if toggle and not await toggle.is_checked():
                await toggle.click()
                await page.wait_for_timeout(1200)
        except Exception as e:
            print(f"      (Socket Mode 토글 스킵: {e})")

        # Generate 버튼
        try:
            await wait_click(
                page,
                'button:has-text("Generate"), a:has-text("Generate")',
                timeout=8000,
            )
        except PWTimeout:
            await wait_click(page, 'text="Generate an app-level token"', timeout=8000)

        await page.wait_for_timeout(1000)

        # 토큰 이름 입력
        token_name_el = await page.wait_for_selector(
            'input[placeholder*="Token Name"], input[placeholder*="token"], input[id*="token-name"]',
            timeout=8000,
        )
        await token_name_el.fill(TOKEN_LABEL)
        await page.wait_for_timeout(400)

        # scope: connections:write 추가
        try:
            scope_input = await page.wait_for_selector(
                'input[placeholder*="scope"], input[id*="scope"]', timeout=6000
            )
            await scope_input.fill("connections:write")
            await page.wait_for_timeout(600)
            await page.click('text="connections:write"', timeout=5000)
            await page.wait_for_timeout(400)
        except PWTimeout:
            print("      (scope 드롭다운 스킵 — 이미 선택됐을 수 있음)")

        # Generate 최종 클릭
        await wait_click(page, 'button:has-text("Generate")', timeout=8000)
        await page.wait_for_timeout(2000)

        # 토큰 텍스트 추출 (xapp-...)
        try:
            code_els = await page.query_selector_all("code, [class*='token']")
            for el in code_els:
                txt = (await el.inner_text()).strip()
                if txt.startswith("xapp-"):
                    doc_app_token = txt
                    break
        except Exception:
            pass

        if not doc_app_token:
            # clipboard 시도
            try:
                await page.click('button[title*="Copy"], button:has-text("Copy")', timeout=4000)
                doc_app_token = await page.evaluate("navigator.clipboard.readText()")
            except Exception:
                pass

        if doc_app_token:
            print(f"      ✓ App-Level Token: {doc_app_token[:30]}...")
        else:
            print("      ⚠ App-Level Token 자동 추출 실패 — 브라우저에서 직접 복사해주세요")
            doc_app_token = input("      xapp-... 토큰 입력: ").strip()

        # Done 버튼 (모달 닫기)
        try:
            await wait_click(page, 'button:has-text("Done")', timeout=5000)
        except PWTimeout:
            pass

        # ── 4. Event Subscriptions ─────────────────────────────────────────
        print("[4/7] Event Subscriptions 설정...")
        await page.goto(
            f"https://api.slack.com/apps/{app_id}/event-subscriptions",
            wait_until="networkidle",
        )
        await page.wait_for_timeout(1500)

        # Enable 토글
        try:
            toggle = await page.query_selector('input[type="checkbox"]')
            if toggle and not await toggle.is_checked():
                await toggle.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        # Bot Events — message.channels 추가
        try:
            await wait_click(page, 'button:has-text("Add Bot User Event")', timeout=8000)
            await page.wait_for_timeout(400)
            search = await page.wait_for_selector(
                'input[type="search"], input[placeholder*="Search"]', timeout=6000
            )
            await search.fill("message.channels")
            await page.wait_for_timeout(800)
            await page.click('div[class*="option"]:has-text("message.channels")', timeout=5000)
            await page.wait_for_timeout(500)
        except PWTimeout:
            print("      (message.channels 이벤트 추가 스킵)")

        # Save Changes
        try:
            await wait_click(page, 'button:has-text("Save Changes")', timeout=6000)
            await page.wait_for_timeout(1000)
        except PWTimeout:
            pass

        print("      ✓ Event Subscriptions 완료")

        # ── 5. OAuth & Permissions — Bot Scopes ───────────────────────────
        print("[5/7] Bot Token Scopes 추가...")
        await page.goto(
            f"https://api.slack.com/apps/{app_id}/oauth",
            wait_until="networkidle",
        )
        await page.wait_for_timeout(1500)

        for scope in ["chat:write", "files:write", "channels:history"]:
            try:
                await wait_click(
                    page,
                    'button:has-text("Add an OAuth Scope")',
                    timeout=6000,
                )
                await page.wait_for_timeout(400)
                search = await page.wait_for_selector(
                    'input[placeholder*="Search"], input[type="search"]', timeout=5000
                )
                await search.fill(scope)
                await page.wait_for_timeout(600)
                await page.click(
                    f'div[class*="option"]:has-text("{scope}"), li:has-text("{scope}")',
                    timeout=5000,
                )
                await page.wait_for_timeout(500)
                print(f"      + {scope}")
            except Exception as e:
                print(f"      ! {scope} 추가 실패: {e}")

        # ── 6. Install to Workspace ────────────────────────────────────────
        print("[6/7] 워크스페이스에 설치...")
        try:
            install_btn = await page.wait_for_selector(
                'a:has-text("Install to"), button:has-text("Install to")',
                timeout=8000,
            )
            await install_btn.scroll_into_view_if_needed()
            await install_btn.click()
            await page.wait_for_timeout(2000)

            # OAuth Allow 버튼
            try:
                await wait_click(page, 'button:has-text("Allow")', timeout=10000)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)
            except PWTimeout:
                pass
            print("      ✓ 설치 완료")
        except PWTimeout:
            print("      ⚠ 설치 버튼 찾기 실패 — 수동으로 설치 후 Enter")
            input("      설치 완료 후 Enter...")

        # ── 7. Bot Token 추출 ──────────────────────────────────────────────
        print("[7/7] Bot Token 추출...")
        await page.goto(
            f"https://api.slack.com/apps/{app_id}/oauth",
            wait_until="networkidle",
        )
        await page.wait_for_timeout(1500)

        # xoxb- 토큰 찾기
        try:
            code_els = await page.query_selector_all("code, input[value^='xoxb']")
            for el in code_els:
                txt = await el.inner_text() if await el.inner_text() else await el.get_attribute("value")
                if txt and txt.strip().startswith("xoxb-"):
                    doc_bot_token = txt.strip()
                    break
        except Exception:
            pass

        if not doc_bot_token:
            # 마스킹된 토큰 옆 Copy 버튼 클릭 후 클립보드 읽기
            try:
                copy_btns = await page.query_selector_all(
                    'button[title*="Copy"], button:has-text("Copy")'
                )
                for btn in copy_btns:
                    await btn.click()
                    await page.wait_for_timeout(400)
                    val = await page.evaluate("navigator.clipboard.readText()")
                    if val.startswith("xoxb-"):
                        doc_bot_token = val
                        break
            except Exception:
                pass

        if doc_bot_token:
            print(f"      ✓ Bot Token: {doc_bot_token[:30]}...")
        else:
            print("      ⚠ Bot Token 자동 추출 실패")
            doc_bot_token = input("      xoxb-... 토큰 입력: ").strip()

        await browser.close()

        # ── .env 업데이트 ──────────────────────────────────────────────────
        print("\n▶ .env 업데이트...")
        env_text = DOTENV_PATH.read_text(encoding="utf-8")

        if doc_bot_token:
            env_text = re.sub(r"DOC_BOT_TOKEN=.*", f"DOC_BOT_TOKEN={doc_bot_token}", env_text)
        if doc_app_token:
            env_text = re.sub(r"DOC_APP_TOKEN=.*", f"DOC_APP_TOKEN={doc_app_token}", env_text)

        DOTENV_PATH.write_text(env_text, encoding="utf-8")

        print("\n" + "=" * 60)
        print("✅ 완료!")
        print(f"  DOC_BOT_TOKEN: {doc_bot_token[:35]}..." if doc_bot_token else "  DOC_BOT_TOKEN: 미추출")
        print(f"  DOC_APP_TOKEN: {doc_app_token[:35]}..." if doc_app_token else "  DOC_APP_TOKEN: 미추출")
        print("\n다음 단계:")
        print("  1. 채널에 봇 초대: /invite @Sandbox Doc Bot")
        print("  2. 봇 재실행")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
