#!/usr/bin/env python3
"""work/award-hits.json を works.json の awardResults に反映する(冪等)。"""
import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
src = ROOT / "public/data/source/works.json"
hits = json.load(open(ROOT / "work/award-hits.json", encoding="utf-8"))
works = json.load(open(src, encoding="utf-8"))
today = datetime.date.today().isoformat()
n = 0
for w in works:
    rs = hits.get(w["id"])
    if not rs:
        continue
    seen = set()
    merged = []
    for r in (w.get("awardResults") or []) + rs:
        k = (r["awardId"], r["year"], r["result"])
        if k in seen:
            continue
        seen.add(k)
        merged.append({"awardId": r["awardId"], "year": r["year"], "result": r["result"]})
    merged.sort(key=lambda r: (r["awardId"], r["year"], r["result"]))
    if merged != (w.get("awardResults") or []):
        w["awardResults"] = merged
        note = w.get("sourceNote", "")
        if "受賞歴" not in note:
            w["sourceNote"] = (note + " 受賞歴はWikipediaの各賞ページで裏取り(%s)。" % today).strip()
        w["updatedAt"] = today
        n += 1
json.dump(works, open(src, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("更新した作品:", n, " 総受賞歴:", sum(len(w.get("awardResults") or []) for w in works))
