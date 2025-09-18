import csv
import re

# --- Files ---
INPUT_CSV = "linkedin_contacts_final_size.csv"
OUTPUT_CSV = "linkedin_contacts_final_size_filtered.csv"

# --- Allowed size range ---
MIN_EMPLOYEES = 11
MAX_EMPLOYEES = 200

# --- Helper to convert K/M to int ---
def parse_number(num_str):
    num_str = num_str.strip().upper()
    if "K" in num_str:
        return int(float(num_str.replace("K", "")) * 1000)
    elif "M" in num_str:
        return int(float(num_str.replace("M", "")) * 1000000)
    else:
        return int(num_str)

# --- Function to parse size string ---
def parse_size(size_str):
    if not size_str or size_str.lower() == "n/a":
        return None, None
    size_str = size_str.replace(",", "").replace(" employees", "").strip()
    
    if "+" in size_str:
        min_emp = parse_number(re.search(r"(\d+\.?\d*)([KM]?)", size_str).group())
        return min_emp, None
    elif "-" in size_str:
        parts = size_str.split("-")
        min_emp = parse_number(parts[0])
        max_emp = parse_number(parts[1])
        return min_emp, max_emp
    else:
        try:
            num = parse_number(size_str)
            return num, num
        except:
            return None, None

# --- Read, filter, save ---
filtered_rows = []
with open(INPUT_CSV, newline="", encoding="utf-8") as infile:
    reader = csv.DictReader(infile)
    for row in reader:
        min_emp, max_emp = parse_size(row.get("Company_Size", ""))
        if min_emp is None:
            continue
        # Check if size overlaps with 11-200 range
        if max_emp is None:  # e.g., "10K+" -> skip
            continue
        if max_emp < MIN_EMPLOYEES or min_emp > MAX_EMPLOYEES:
            continue
        filtered_rows.append(row)

# Save filtered CSV
if filtered_rows:
    fieldnames = filtered_rows[0].keys()
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)

print(f"✅ Filtered CSV saved as '{OUTPUT_CSV}' ({len(filtered_rows)} companies)")
