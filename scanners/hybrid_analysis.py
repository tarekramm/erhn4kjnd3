import os
import pandas as pd
import requests
import time

# API Credentials (Replace with your actual keys)
API_KEY = "..."
SECRET = "..."


#  Correct Hybrid Analysis API Endpoint
HYBRID_ANALYSIS_FEED_API = "https://www.hybrid-analysis.com/api/v2/feed/latest"

# Excel File Path
excel_path = "....xlsx"

# API Headers
headers = {
    "User-Agent": "Falcon Sandbox",
    "api-key": API_KEY,
    "secret": SECRET,
    "accept": "application/json"
}

# Function to Fetch Latest Reports


def fetch_latest_reports():
    response = requests.get(HYBRID_ANALYSIS_FEED_API, headers=headers)

    if response.status_code == 200:
        results = response.json().get("data", [])
        urls = []

        for entry in results:
            if "submit_name" in entry and entry["submit_name"].startswith("http"):
                urls.append(entry["submit_name"])  # Extract URLs

        print(f" API Returned: {len(urls)} URLs in this run")  # Debugging
        return urls
    else:
        print(f" Error: {response.status_code} - {response.text}")
        return []

# Function to Append ONLY New URLs to Excel


def save_to_excel(new_urls):
    # Load existing data or create new DataFrame
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path, engine="openpyxl")
        # Convert to set for fast lookup
        existing_urls = set(df["Extracted URLs"].tolist())
    else:
        df = pd.DataFrame(columns=["Extracted URLs"])
        existing_urls = set()

    # Filter only truly new URLs
    unique_new_urls = [url for url in new_urls if url not in existing_urls]

    if unique_new_urls:
        new_df = pd.DataFrame(unique_new_urls, columns=["Extracted URLs"])
        df = pd.concat([df, new_df], ignore_index=True)  # Append new data
        # Save back to Excel
        df.to_excel(excel_path, index=False, engine="openpyxl")
        print(
            f" {len(unique_new_urls)} new URLs added. Total in Excel: {len(df)}\n")
    else:
        print(" No new unique URLs found. Skipping save.")


# Run Every 2 Seconds (900 Runs)
run_count = 0
total_runs = 900

while run_count < total_runs:
    print(f"\n Running Scan {run_count + 1} of {total_runs}...")

    urls = fetch_latest_reports()
    if urls:
        save_to_excel(urls)
    else:
        print(" No new URLs found.")

    run_count += 1
    time.sleep(2)  # Wait 2 seconds before next run

print(f"\n Script finished after {run_count} runs.")

