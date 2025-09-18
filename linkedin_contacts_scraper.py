import os
import time
import pandas as pd
import requests
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import json

# --- Load environment variables ---
load_dotenv()
SERPER_KEY = os.getenv("SERPER_KEY")
if not SERPER_KEY:
    raise ValueError("SERPER_KEY not found in environment variables.")

# --- Input / Output ---
INPUT_CSV = "linkedin_contacts_final_size_filtered.csv"
OUTPUT_CSV = "linkedin_contacts_final_contacts.csv"
CACHE_JSON = "linkedin_contacts_cache.json"

# --- Settings ---
ROLES = [
    "CEO", "Founder",
    "Head Marketing", "VP Marketing", "Vice President Marketing", "Chief Marketing Officer",
    "Director", "Senior Marketing Manager", "Marketing Manager", "Manager"
]
ROLE_EQUIVALENTS = {
    "VP Marketing": "Vice President Marketing",
    "Vice President Marketing": "VP Marketing"
}
MAX_PROFILES_PER_COMPANY = 4
NUM_THREADS = 3
SLEEP_BETWEEN_QUERIES = 2
MAX_RETRIES = 3
PARTIAL_SAVE_EVERY = 5  # save CSV every N companies

# --- Cache functions ---
def load_cache():
    if os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_JSON, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

# --- Clean roles ---
def clean_role(title, company_name):
    if not title:
        return ""
    title = re.sub(re.escape(company_name), "", title, flags=re.IGNORECASE)
    title = re.sub(r"(,?\s*(India|United States|Singapore|California|New York|UK|USA|San Francisco|Bangalore|Hyderabad|Mumbai))", "", title, flags=re.IGNORECASE)
    junk_words = ["Ltd", "Limited", "Pvt", "Private", "LLC", "Group", "Inc"]
    for j in junk_words:
        title = title.replace(j, "")
    title = re.sub(r'[^\x00-\x7F]+','', title)
    for sep in ["|", "-", ",", "•", "–"]:
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            if parts:
                title = parts[0]
                break
    keywords = ["CEO", "Founder", "Marketing", "Director", "Manager", "VP", "Chief", "Head", "Lead", "Senior"]
    if any(k.lower() in title.lower() for k in keywords):
        return title.strip()
    return ""

# --- Extract profiles using Serper ---
def search_profiles(company_name, role):
    headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
    search_patterns = [
        f'{role} at {company_name}',
        f'{company_name} {role}',
        f'{role} {company_name} LinkedIn'
    ]
    profiles = []
    seen_urls = set()

    for pattern in search_patterns:
        for attempt in range(MAX_RETRIES):
            try:
                payload = {"q": pattern, "num": 5}
                resp = requests.post("https://google.serper.dev/search", headers=headers, json=payload, timeout=30)
                resp.raise_for_status()
                results = resp.json()
                for item in results.get("organic", []):
                    link = item.get("link", "")
                    title = item.get("title", "")
                    if "linkedin.com/in/" in link and link not in seen_urls:
                        seen_urls.add(link)
                        name = title.split(" - ")[0].strip()
                        role_cleaned = clean_role(" - ".join(title.split(" - ")[1:]), company_name) or role
                        if role_cleaned:
                            profiles.append({
                                "name": name,
                                "role": role_cleaned,
                                "url": link
                            })
                            if len(profiles) >= MAX_PROFILES_PER_COMPANY:
                                return profiles
                if profiles:
                    break
            except requests.exceptions.HTTPError as e:
                if resp.status_code == 429:
                    wait_time = 2 ** attempt
                    print(f"❌ 429 Too Many Requests for '{pattern}', retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Error for '{pattern}': {e}")
                    break
            except Exception as e:
                print(f"❌ Error for '{pattern}': {e}")
                break
        if profiles:
            break
    return profiles

# --- Worker for threading ---
def worker(company_row, cache):
    company_name = company_row["companyName"]
    if company_name in cache:
        return company_row, cache[company_name]

    found_profiles = []
    skipped_roles = set()

    for role in ROLES:
        if len(found_profiles) >= MAX_PROFILES_PER_COMPANY:
            break
        if role in skipped_roles:
            continue

        profiles = search_profiles(company_name, role)
        for p in profiles:
            if len(found_profiles) < MAX_PROFILES_PER_COMPANY:
                found_profiles.append(p)
            else:
                break

        if role in ROLE_EQUIVALENTS and profiles:
            skipped_roles.add(ROLE_EQUIVALENTS[role])

    cache[company_name] = found_profiles
    return company_row, found_profiles

# --- Main ---
def main():
    df = pd.read_csv(INPUT_CSV)
    cache = load_cache()
    results_rows = []

    companies_to_process = df.to_dict(orient="records")

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = [executor.submit(worker, row, cache) for row in companies_to_process]
        for idx, future in enumerate(as_completed(futures), 1):
            company_row, profiles = future.result()
            row_dict = company_row.copy()  # keep all original columns

            for i in range(MAX_PROFILES_PER_COMPANY):
                if i < len(profiles):
                    row_dict[f"Contact{i+1}_Name"] = profiles[i].get("name", "")
                    row_dict[f"Contact{i+1}_Role"] = profiles[i].get("role", "")
                    row_dict[f"Contact{i+1}_LinkedIn_URL"] = profiles[i].get("url", "")
                else:
                    row_dict[f"Contact{i+1}_Name"] = ""
                    row_dict[f"Contact{i+1}_Role"] = ""
                    row_dict[f"Contact{i+1}_LinkedIn_URL"] = ""

            results_rows.append(row_dict)
            print(f"✅ Processed: {company_row['companyName']} ({len(profiles)} contacts)")

            # --- Partial saving ---
            if idx % PARTIAL_SAVE_EVERY == 0:
                pd.DataFrame(results_rows).to_csv(OUTPUT_CSV, index=False)
                save_cache(cache)
                print(f"💾 Partial save after {idx} companies.")

            time.sleep(SLEEP_BETWEEN_QUERIES)

    # --- Final save ---
    final_df = pd.DataFrame(results_rows)
    final_df.to_csv(OUTPUT_CSV, index=False)
    save_cache(cache)
    print(f"\n✔ Done! CSV saved as '{OUTPUT_CSV}' with contacts added.")

if __name__ == "__main__":
    main()
