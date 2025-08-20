import asyncio
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEATMAP_PNG = os.path.join(OUTPUT_DIR, "sp500_heatmap.png")

async def capture_sp500_heatmap(context):
    url = "https://finviz.com/map.ashx"
    page = await context.new_page()
    print(f"[Heatmap] Navigating… {url}")
    await page.goto(url, wait_until="load")
    # Allow extra time for the dynamic image/tiles to render
    await asyncio.sleep(5)

    # Try to accept any cookie banners (best-effort)
    for sel in [
        'button:has-text("Accept")', 'button:has-text("I Accept")',
        'button:has-text("Agree")', ('role', 'button', 'Accept'),
        '[aria-label*="accept"]'
    ]:
        try:
            if isinstance(sel, tuple):
                _, role, name = sel
                await page.get_by_role(role, name=name).click(timeout=1500)
            else:
                await page.locator(sel).first.click(timeout=1500)
            await asyncio.sleep(0.5)
            break
        except:
            pass

    # Prefer to screenshot the map area; fall back to full page
    selectors = [
        '#map',                   # main container Finviz uses
        'div[id*="map"]',
        'img[src*="map.ashx"]',   # the generated heatmap image
        'canvas'                  # if they render via canvas
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.screenshot(path=HEATMAP_PNG)
                print(f"[Heatmap][OK] Saved element: {HEATMAP_PNG}")
                await page.close()
                return True
        except:
            continue

    # Fallback: full page (ensures we always produce an image)
    await page.screenshot(path=HEATMAP_PNG, full_page=True)
    print(f"[Heatmap][OK] Saved full page: {HEATMAP_PNG}")
    await page.close()
    return True

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1200},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )
        await capture_sp500_heatmap(context)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
