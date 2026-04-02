"""현재 Slack API 페이지 상태 스크린샷 + 버튼 목록 출력"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300, args=["--start-maximized"])
        ctx = await browser.new_context(no_viewport=True)
        page = await ctx.new_page()

        await page.goto("https://api.slack.com/apps", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        print(f"\nURL: {page.url}")
        print(f"Title: {await page.title()}")

        # 모든 버튼/링크 텍스트 출력
        buttons = await page.query_selector_all("button, a")
        print("\n=== 버튼/링크 목록 (최대 30개) ===")
        seen = set()
        for el in buttons[:50]:
            try:
                txt = (await el.inner_text()).strip()
                if txt and txt not in seen and len(txt) < 80:
                    seen.add(txt)
                    print(f"  [{await el.tag_name()}] {txt!r}")
            except Exception:
                pass

        await page.screenshot(path="slack_debug.png", full_page=False)
        print("\n스크린샷 저장됨: slack_debug.png")
        print("\nEnter 누르면 브라우저 종료...")
        input()
        await browser.close()

asyncio.run(main())
