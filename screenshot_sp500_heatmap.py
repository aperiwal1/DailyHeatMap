import asyncio, os, random
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)
HEATMAP_PNG = os.path.join(OUTPUT_DIR, "sp500_heatmap.png")
URL = "https://finviz.com/map.ashx"

REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

async def goto_with_retries(page, url, attempts=3):
    last_err = None
    for i in range(1, attempts + 1):
        try:
            print(f"[Heatmap] goto attempt {i}/{attempts} …")
            # faster ‘domcontentloaded’ first, then wait for network idle
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            return True
        except Exception as e:
            last_err = e
            await asyncio.sleep(2 + i)  # backoff
    print(f"[Heatmap][ERR] goto failed: {last_err}")
    return False

async def capture_sp500_heatmap(context):
    page = await context.new_page()

    # small stealth tweaks
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
    """)

    print(f"[Heatmap] Navigating… {URL}")
    ok = await goto_with_retries(page, URL, attempts=3)
    if not ok:
        # last resort: try again with ‘load’ wait_until
        try:
            await page.goto(URL, wait_until="load", timeout=120000)
        except Exception as e:
            print(f"[Heatmap][FATAL] Could not load page: {e}")
            raise

    # accept cookies / consent (best effort)
    for sel in [
        'button:has-text("Accept")', 'button:has-text("I Accept")',
        'button:has-text("Agree")',  '[aria-label*="accept"]',
        ('role','button','Accept')
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

    # wait for the map container or the rendered image
    try:
        await page.wait_for_selector('#map, img[src*="map.ashx"], div[id*="map"]',
                                     state="visible", timeout=60000)
    except PWTimeout:
        print("[Heatmap][WARN] Map selector not found; will screenshot full page.")

    # Try element screenshot first
    for sel in ['#map', 'div[id*="map"]', 'img[src*="map.ashx"]', 'canvas']:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.screenshot(path=HEATMAP_PNG)
                print(f"[Heatmap][OK] Saved element: {HEATMAP_PNG}")
                await page.close()
                return True
        except:
            continue

    # Fallback: full page
    await page.screenshot(path=HEATMAP_PNG, full_page=True)
    print(f"[Heatmap][OK] Saved full page: {HEATMAP_PNG}")
    await page.close()
    return True

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1200},
            user_agent=REAL_UA,
            java_script_enabled=True,
            accept_downloads=False,
        )
        await capture_sp500_heatmap(context)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
