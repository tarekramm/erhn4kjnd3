
import io
import gzip
import json
import sqlite3
import requests
import concurrent.futures
import threading
import queue
import time
import signal
from collections import Counter

CRAWLS = [
    # 2025
    # CC-MAIN-2025-38, CC-MAIN-2025-35, CC-MAIN-2025-34, CC-MAIN-2025-30, CC-MAIN-2025-24,
    # CC-MAIN-2025-18, CC-MAIN-2025-10, CC-MAIN-2025-06,
    # # 2024
    CC-MAIN-2024-50, CC-MAIN-2024-46, CC-MAIN-2024-42, CC-MAIN-2024-38,
    CC-MAIN-2024-33, CC-MAIN-2024-30, CC-MAIN-2024-26, CC-MAIN-2024-22,
    CC-MAIN-2024-18, CC-MAIN-2024-14, CC-MAIN-2024-10, CC-MAIN-2024-06,
    # 2023
    # CC-MAIN-2023-50, CC-MAIN-2023-45, CC-MAIN-2023-40, CC-MAIN-2023-34,
    # CC-MAIN-2023-28, CC-MAIN-2023-23, CC-MAIN-2023-17, CC-MAIN-2023-10, CC-MAIN-2023-06,
    # # 2022
    # CC-MAIN-2022-49, CC-MAIN-2022-40, CC-MAIN-2022-33, CC-MAIN-2022-27,
    # CC-MAIN-2022-21, CC-MAIN-2022-14, CC-MAIN-2022-05,
    # # 2021
    # CC-MAIN-2021-49, CC-MAIN-2021-43, CC-MAIN-2021-38, CC-MAIN-2021-31,
    # CC-MAIN-2021-25, CC-MAIN-2021-17, CC-MAIN-2021-10, CC-MAIN-2021-04,
    # # 2020
    # CC-MAIN-2020-50, CC-MAIN-2020-45, CC-MAIN-2020-40, CC-MAIN-2020-34,
    # CC-MAIN-2020-29, CC-MAIN-2020-24, CC-MAIN-2020-16, CC-MAIN-2020-10,
    # # 2019
    # CC-MAIN-2019-51, CC-MAIN-2019-47, CC-MAIN-2019-43, CC-MAIN-2019-39,
    # CC-MAIN-2019-35, CC-MAIN-2019-30, CC-MAIN-2019-26, CC-MAIN-2019-22,
    # CC-MAIN-2019-18, CC-MAIN-2019-13, CC-MAIN-2019-09, CC-MAIN-2019-04,
    # # 2018
    # CC-MAIN-2018-51, CC-MAIN-2018-47, CC-MAIN-2018-43, CC-MAIN-2018-39,
    # CC-MAIN-2018-34, CC-MAIN-2018-30, CC-MAIN-2018-26, CC-MAIN-2018-22,
    # CC-MAIN-2018-17, CC-MAIN-2018-13, CC-MAIN-2018-09, CC-MAIN-2018-05,
    # # 2017
    # CC-MAIN-2017-51, CC-MAIN-2017-47, CC-MAIN-2017-43, CC-MAIN-2017-39,
    # CC-MAIN-2017-34, CC-MAIN-2017-30, CC-MAIN-2017-26, CC-MAIN-2017-22,
    # CC-MAIN-2017-17, CC-MAIN-2017-13, CC-MAIN-2017-09, CC-MAIN-2017-04,
    # # 2016
    # CC-MAIN-2016-50, CC-MAIN-2016-44, CC-MAIN-2016-40, CC-MAIN-2016-36,
    # CC-MAIN-2016-30, CC-MAIN-2016-26, CC-MAIN-2016-22, CC-MAIN-2016-18,
    # CC-MAIN-2016-07,
    # # 2015
    # CC-MAIN-2015-48, CC-MAIN-2015-40, CC-MAIN-2015-35, CC-MAIN-2015-32,
    # CC-MAIN-2015-27, CC-MAIN-2015-22, CC-MAIN-2015-18, CC-MAIN-2015-14,
    # CC-MAIN-2015-11, CC-MAIN-2015-06,
    # # 2014
    # CC-MAIN-2014-52, CC-MAIN-2014-49, CC-MAIN-2014-42, CC-MAIN-2014-41,
    # CC-MAIN-2014-35, CC-MAIN-2014-23, CC-MAIN-2014-15, CC-MAIN-2014-10,
    # # 2013
    # CC-MAIN-2013-48, CC-MAIN-2013-20
]


BASE = httpsdata.commoncrawl.orgcc-indexcollections

DB = ".db"
TABLE = urls
COLUMN = urls   # primary key

TARGET = 40_000_000          # stop after this many rows in DB
WITH_QUERY_ONLY = False     # True - keep only URLs containing 
ONLY_HTTPS = False          # True - keep only https

WORKERS = 64                # shard fetchers
Q_MAX = 1_000_000           # in-memory queue capacity
DB_BATCH = 50_000           # insert batch size

UA = ...
TIMEOUT = (5, 60)
MAX_SHARDS_PER_CRAWL = 20000
CONSEC_404_STOP = 40        # stop a crawl after many consecutive 404 shards
STATUS_EVERY_SEC = 10

# ---------- globals ----------
STATS = Counter()
_stop_evt = threading.Event()

# ---------- helpers ----------


def init_db(path)
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute(PRAGMA journal_mode=WAL)
    con.execute(PRAGMA synchronous=OFF)
    con.execute(PRAGMA temp_store=MEMORY)
    con.execute(PRAGMA cache_size=-500000)
    con.execute(
        f'CREATE TABLE IF NOT EXISTS {TABLE}({COLUMN} TEXT PRIMARY KEY)')
    return con


def passes(u)
    if not u
        return False
    if ONLY_HTTPS and not u.startswith(https)
        return False
    if WITH_QUERY_ONLY and  not in u
        return False
    return True


def stream_shard(sess, url, out_q)
    with sess.get(url, stream=True, timeout=TIMEOUT) as r
        if r.status_code == 404
            return False  # signals a gap
        r.raise_for_status()
        gz = gzip.GzipFile(fileobj=r.raw)
        for raw in gz
            if _stop_evt.is_set()
                break
            line = raw.decode(utf-8, errors=ignore).strip()
            if not line
                continue
            try
                if line.startswith({)
                    obj = json.loads(line)
                else
                    k = line.find( {)
                    if k == -1
                        continue
                    obj = json.loads(line[k+1])
                u = obj.get(url)
                if passes(u)
                    out_q.put(u)
                    STATS[enq] += 1
            except Exception
                continue
    return True


def enumerate_shards(crawl)
    base = f{BASE}{crawl}indexes
    for n in range(MAX_SHARDS_PER_CRAWL)
        yield f{base}cdx-{n05d}.gz


def writer(con, in_q, target)
    cur = con.cursor()
    buf = []
    saved = cur.execute(fSELECT COUNT(1) FROM {TABLE}).fetchone()[0]
    STATS[rows] = saved
    last_log = time.time()
    while not (_stop_evt.is_set() and in_q.empty())
        try
            u = in_q.get(timeout=0.5)
        except queue.Empty
            continue
        buf.append((u,))
        if len(buf) = DB_BATCH
            cur.executemany(
                f'INSERT OR IGNORE INTO {TABLE}({COLUMN}) VALUES ()', buf)
            con.commit()
            buf.clear()
            saved = cur.execute(fSELECT COUNT(1) FROM {TABLE}).fetchone()[0]
            STATS[rows] = saved
            now = time.time()
            if now - last_log = 5
                print(frows={saved}, flush=True)
                last_log = now
            if saved = target
                _stop_evt.set()
                break
    if buf
        cur.executemany(
            f'INSERT OR IGNORE INTO {TABLE}({COLUMN}) VALUES ()', buf)
        con.commit()


def status_loop(start_ts, in_q)
    prev_rows = STATS.get(rows, 0)
    while not _stop_evt.is_set()
        time.sleep(STATUS_EVERY_SEC)
        rows = STATS.get(rows, 0)
        rps = (rows - prev_rows)  max(1, STATUS_EVERY_SEC)
        prev_rows = rows
        elapsed = max(1, time.time() - start_ts)
        avg = rows  elapsed
        print(
            f[status] rows={rows} rate={rps.0f}s avg={avg.0f}s 
            fq={in_q.qsize()} shards_ok={STATS.get('shards_ok', 0)} 
            f404={STATS.get('shards_404', 0)} err={STATS.get('shards_err', 0)} enq={STATS.get('enq', 0)},
            flush=True
        )


def task(sess, shard_url, out_q)
    try
        ok = stream_shard(sess, shard_url, out_q)
        if ok
            STATS[shards_ok] += 1
        else
            STATS[shards_404] += 1
        return ok
    except requests.RequestException
        STATS[shards_err] += 1
        return True  # keep going


def handle_sigint(_a, _b)
    _stop_evt.set()


signal.signal(signal.SIGINT, handle_sigint)

# ---------- main ----------


def main()
    start_ts = time.time()
    con = init_db(DB)
    url_q = queue.Queue(maxsize=Q_MAX)

    wt = threading.Thread(target=writer, args=(
        con, url_q, TARGET), daemon=True)
    wt.start()
    threading.Thread(target=status_loop, args=(
        start_ts, url_q), daemon=True).start()

    s = requests.Session()
    s.headers.update({User-Agent UA, Accept })

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex
        for crawl in CRAWLS
            miss = 0
            futures = []
            for shard_url in enumerate_shards(crawl)
                if _stop_evt.is_set()
                    break
                futures.append(ex.submit(task, s, shard_url, url_q))
                if len(futures) = WORKERS  4
                    for fut in concurrent.futures.as_completed(futures)
                        ok = fut.result()
                        if not ok
                            miss += 1
                            if miss = CONSEC_404_STOP
                                futures = []
                                break
                    futures = []
                    if miss = CONSEC_404_STOP
                        break
            for fut in concurrent.futures.as_completed(futures)
                fut.result()
            if _stop_evt.is_set()
                break

    _stop_evt.set()
    wt.join()
    con.close()
    print(done, flush=True)


if __name__ == __main__
    main()
