import os
import csv
import json
import asyncio
from playwright.async_api import async_playwright

# --- Files ---
INPUT_JSON = "dataset_linkedin-jobs-scraper_filtered.json"
OUTPUT_CSV = "linkedin_contacts_final_size.csv"
CACHE_JSON = "company_size_cache.json"

# --- LinkedIn Session Cookie ---
LINKEDIN_SESSION_COOKIE = os.getenv("LINKEDIN_SESSION_COOKIE")
if not LINKEDIN_SESSION_COOKIE:
    raise ValueError("❌ LINKEDIN_SESSION_COOKIE not found in environment!")

print("✅ Loaded cookie type:", type(LINKEDIN_SESSION_COOKIE))
print("🔑 Cookie preview:", str(LINKEDIN_SESSION_COOKIE)[:25], "...")

# --- Cache functions ---
def load_cache():
    if os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_JSON, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

# --- Partial save CSV ---
def save_csv_partial(results, output_file):
    if results:
        fieldnames = list(results[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"💾 Partial CSV saved with {len(results)} companies")

# --- Function to fetch company size ---
async def fetch_company_size(playwright, company_name, linkedin_url, cache):
    if company_name in cache:
        return cache[company_name]

    if not linkedin_url or not linkedin_url.startswith("http"):
        cache[company_name] = "N/A"
        return "N/A"

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()

    try:
        await context.add_cookies([{
            "name": "li_at",
            "value": str(LINKEDIN_SESSION_COOKIE).strip(),
            "domain": ".linkedin.com",
            "path": "/",
            "httpOnly": True,
            "secure": True
        }])
    except Exception as e:
        print(f"❌ Cookie error for {company_name}: {e}")
        await browser.close()
        cache[company_name] = "N/A"
        return "N/A"

    page = await context.new_page()
    try:
        print(f"🔎 Fetching size for {company_name} ...")
        await page.goto(linkedin_url, timeout=60000)
        size_element = await page.query_selector("a.org-top-card-summary-info-list__info-item-link span")
        if size_element:
            size_text = (await size_element.inner_text()).strip()
            print(f"   → {size_text}")
            cache[company_name] = size_text
            return size_text
        else:
            print("   → Not found")
            cache[company_name] = "N/A"
            return "N/A"
    except Exception as e:
        print(f"⚠️ Error fetching {company_name}: {e}")
        cache[company_name] = "N/A"
        return "N/A"
    finally:
        await browser.close()

# --- Main function ---
async def main():
    # Load filtered JSON
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        companies = json.load(f)

    # Load cache
    cache = load_cache()
    results = []

    async with async_playwright() as playwright:
        for i, company in enumerate(companies, 1):
            company_name = company.get("companyName", "")
            linkedin_url = company.get("companyUrl", "")
            size = await fetch_company_size(playwright, company_name, linkedin_url, cache)
            company["Company_Size"] = size
            results.append(company)

            # Partial save every 5 companies
            if i % 5 == 0:
                save_csv_partial(results, OUTPUT_CSV)
                save_cache(cache)

        # Final save after all companies processed
        save_csv_partial(results, OUTPUT_CSV)
        save_cache(cache)

    print(f"\n✅ All done! CSV saved to {OUTPUT_CSV}")

# --- Run ---
if __name__ == "__main__":
    asyncio.run(main())
