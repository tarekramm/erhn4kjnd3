

import os
import pandas as pd
import requests
import time

#  API Endpoint
URLSCAN_API_ENDPOINT = "https://urlscan.io/api/v1/search/"

#  Search Query (Modify as needed)
QUERY = "page.url:*"

#  Excel File Path
excel_path = "....xlsx"
# Your API key
API_KEY = "..."

#  API Headers

headers = {"API-Key": API_KEY}
params = {"q": QUERY}

#  Function to Fetch URLs


def fetch_urls():
    response = requests.get(URLSCAN_API_ENDPOINT,
                            headers=headers, params=params)
    if response.status_code == 200:
        results = response.json().get("results", [])
        urls = [result.get("page", {}).get("url", "N/A")
                for result in results if result.get("page", {}).get("url")]
        print(f" API Returned: {len(urls)} URLs in this run")  # Debugging
        return urls
    else:
        print(f" Error: {response.status_code} - {response.text}")
        return []

#  Function to Save URLs to Excel


def save_to_excel(new_urls):
    #  Load Existing Data or Create New DataFrame
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path, engine="openpyxl")
    else:
        df = pd.DataFrame(columns=["Extracted URLs"])

    #  Append New URLs and Remove Duplicates
    new_df = pd.DataFrame(new_urls, columns=["Extracted URLs"])
    df = pd.concat([df, new_df], ignore_index=True).drop_duplicates(
    ).reset_index(drop=True)

    #  Save to Excel
    df.to_excel(excel_path, index=False, engine="openpyxl")
    print(f" Total URLs in Excel: {len(df)}\n")  # Debugging


#  Run the Script Every 2 Seconds (Stops After 10 Runs)
run_count = 0
total_runs = 900  # Modify this to change the number of runs

while run_count < total_runs:
    print(f"\n Running Scan {run_count + 1} of {total_runs}...")
    urls = fetch_urls()

    if urls:
        save_to_excel(urls)
    else:
        print(" No new URLs found.")

    run_count += 1
    time.sleep(2)  # Wait 2 seconds before next run

print(f"\n Script finished after {run_count} runs.")

