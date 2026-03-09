
import requests
import pandas as pd
import time
import json
import os
import datetime as dt

BASE = "https://web.archive.org/cdx/search/cdx"
# outputs: wayback_urls_all_1.xlsx, _2.xlsx, ...
OUT_BASE = "wayback_urls_all"
LIMIT = 5000                         # CDX page size
THROTTLE = 1.0                       # seconds between calls
STATE_FILE = "cdx_resume.json"
# optional: one pattern per line (e.g., *.example.com/*)
PATTERNS_FILE = None
DEFAULT_PATTERNS = ["*"]
# Identify yourself; replace with your email or project contact
HEADERS = {"User-Agent": "FilteringURL/1.0 (+contact@example.com)"}


def load_patterns():
    return DEFAULT_PATTERNS


def year_windows(start=1996, end=None, span_years=4):
    if end is None:
        end = dt.datetime.utcnow().year
    wins = []
    y = start
    while y <= end:
        y2 = min(y + span_years - 1, end)
        wins.append((f"{y}0101", f"{y2}1231"))
        y = y2 + 1
    return wins


def load_state(patterns, windows):
    if os.path.exists(STATE_FILE):
        s = json.load(open(STATE_FILE, "r"))
    else:
        s = {"pattern_idx": 0, "window_idx": 0, "offsets": {},
             "file_index": 1, "count_in_file": 0}
    # ensure keys exist
    for pi, p in enumerate(patterns):
        for wi, w in enumerate(windows):
            key = f"{pi}:{wi}"
            s["offsets"].setdefault(key, 0)
    return s


def save_state(s):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, STATE_FILE)


def write_excel_chunk(urls, state):
    """Append URLs to Excel, splitting at 80k rows per file."""
    i = state["file_index"]
    count = state["count_in_file"]
    idx = 0
    while idx < len(urls):
        room = 80000 - count
        take = min(room, len(urls) - idx)
        chunk = urls[idx:idx+take]
        path = f"{OUT_BASE}_{i}.xlsx"
        if count == 0 or not os.path.exists(path):
            pd.DataFrame({"url": chunk}).to_excel(path, index=False)
        else:
            old = pd.read_excel(path)
            pd.concat([old, pd.DataFrame({"url": chunk})], ignore_index=True).to_excel(
                path, index=False)
        count += take
        idx += take
        if count >= 80000:
            i += 1
            count = 0
    state["file_index"] = i
    state["count_in_file"] = count


def fetch_page(pattern, frm, to, offset):
    params = {
        "url": pattern,
        "matchType": "prefix",
        "output": "json",
        "fl": "original",
        "limit": LIMIT,
        "offset": offset,
        "from": frm,
        "to": to,
    }
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=60)
    if r.status_code in (429, 503):
        # backoff for rate limiting
        time.sleep(5)
        r = requests.get(BASE, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    rows = data[1:] if data and data[0] == ["original"] else data
    return [row[0] for row in rows] if rows else []

# ---- main ----


def main():
    patterns = load_patterns()
    
    windows = year_windows(start=1996, span_years=4)
    state = load_state(patterns, windows)
    buffer = []

    for pi in range(state["pattern_idx"], len(patterns)):
        patt = patterns[pi]
        for wi in range(state["window_idx"] if pi == state["pattern_idx"] else 0, len(windows)):
            frm, to = windows[wi]
            key = f"{pi}:{wi}"
            offset = state["offsets"][key]

            while True:
                try:
                    urls = fetch_page(patt, frm, to, offset)
                except requests.HTTPError as e:
                    code = e.response.status_code if e.response is not None else None
                    # 403: skip this pattern/window; 400-range others: skip; 500: brief backoff then skip
                    if code == 403:
                        print(
                            f"403 on {patt} {frm}-{to}, skipping this window")
                        break
                    elif 400 <= code < 500:
                        print(f"{code} on {patt} {frm}-{to}, skipping window")
                        break
                    else:
                        print(
                            f"{code} on {patt} {frm}-{to}, backing off 5s then skipping")
                        time.sleep(5)
                        break

                if not urls:
                    break

                # fast per-page dedupe
                seen = set()
                page_urls = [u for u in urls if not (u in seen or seen.add(u))]
                buffer.extend(page_urls)

                if len(buffer) >= 20000:
                    write_excel_chunk(buffer, state)
                    buffer.clear()

                offset += len(urls)
                state["offsets"][key] = offset
                state["pattern_idx"] = pi
                state["window_idx"] = wi
                save_state(state)
                time.sleep(THROTTLE)

            # end window: flush remainder
            if buffer:
                write_excel_chunk(buffer, state)
                buffer.clear()
            state["window_idx"] = wi + 1
            save_state(state)

        # end pattern
        state["pattern_idx"] = pi + 1
        state["window_idx"] = 0
        save_state(state)

    print(
        f"Done. Last file index: {state['file_index']}, rows in current file: {state['count_in_file']}")


if __name__ == "__main__":
    main()

