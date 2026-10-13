#!/usr/bin/env python3
"""Fetch Jordanian legislation from the Legislation and Opinion Bureau (lob.gov.jo).

Usage: jo_fetch.py [RAW_DIR] [--types 1,2,3,4,5] [--workers 2]

1. lists every legislation of each type via GetLegislationSearch (10 per page);
2. fetches GetLegislationDetails (+ GetlegislationModified, the amendment list) for each.
Everything is cached as JSON under RAW_DIR (default ../../_raw/jo) so re-runs resume.
"""
import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jo_client import LobClient  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def search_data(t):
    return json.dumps(dict(LegislationType=t, LegislationTitle="", LegislationNumber=-1,
                           LegislationYear=-1, LegislationYearTo=-1, LegislationYearFrom=-1,
                           LegislationStatus=-1, MatchingSearch=0, ArticleSearch=0,
                           ArticleText="", Issuer=0, CourtType=0, FromHome=0))


def list_type(c, raw, t):
    fn = os.path.join(raw, "list", f"type{t}.json")
    if os.path.exists(fn):
        return json.load(open(fn))
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    out, page, total = [], 1, None
    while True:
        r = c.call("GetLegislationSearch", {"LangID": 0, "PageIndex": page,
                                            "SearchData": search_data(t)})["Value"]
        total = int(r["TotalPages"])
        out.extend(r["List"])
        print(f"type {t} page {page}/{total} ({len(out)})", flush=True)
        if page >= total or not r["List"]:
            break
        page += 1
    json.dump(out, open(fn, "w"), ensure_ascii=False)
    return out


_local = threading.local()


def client():
    if not hasattr(_local, "c"):
        _local.c = LobClient(delay=1.0)
    return _local.c


def fetch_one(raw, item):
    t, i = item["Type"], item["pmk_ID"]
    d = os.path.join(raw, "det", str(t))
    fn = os.path.join(d, f"{i}{'m' if item.get('isMod') else ''}.json")
    if os.path.exists(fn):
        return
    c = client()
    p = {"LangID": 0, "LegislationID": i, "LegislationType": t}
    det = c.call("GetLegislationDetails", dict(p, isMod="true" if item.get("isMod") else "false"))
    mods = c.call("GetlegislationModified", p)
    os.makedirs(d, exist_ok=True)
    tmp = fn + ".tmp"
    json.dump({"item": item, "details": det.get("Value"), "modified": mods.get("Value")},
              open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, fn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="?", default=os.path.join(HERE, "..", "..", "_raw", "jo"))
    ap.add_argument("--types", default="1,2,3,4,5")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--lists-only", action="store_true")
    a = ap.parse_args()
    c = LobClient()
    items = []
    for t in [int(x) for x in a.types.split(",")]:
        items += list_type(c, a.raw, t)
    print(len(items), "items", flush=True)
    if a.lists_only:
        return
    done = [0]
    lock = threading.Lock()

    def job(it):
        for attempt in range(3):
            try:
                fetch_one(a.raw, it)
                break
            except Exception as e:  # noqa: BLE001
                print("ERR", it["Type"], it["pmk_ID"], e, flush=True)
        with lock:
            done[0] += 1
            if done[0] % 100 == 0:
                print("done", done[0], "/", len(items), flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(job, items))


if __name__ == "__main__":
    main()
