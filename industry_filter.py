import json

# --- Input / Output files ---
INPUT_JSON = "dataset_linkedin-jobs-scraper.json"
OUTPUT_JSON = "dataset_linkedin-jobs-scraper_filtered.json"

# --- Allowed sectors ---
ALLOWED_SECTORS = ["IT Services and IT Consulting", "Software Development"]

# --- Load input JSON ---
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

# --- Filter companies ---
filtered_data = [company for company in data if company.get("sector", "") in ALLOWED_SECTORS]

# --- Save filtered JSON ---
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(filtered_data, f, indent=2)

print(f"✅ Filtered dataset saved as '{OUTPUT_JSON}' ({len(filtered_data)} companies kept)")
