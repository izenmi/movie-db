#!/usr/bin/env python3
"""Wikipediaの各賞ページから受賞作を抽出し、works.json と突合する。

出力: work/award-hits.json  {workId: [{awardId, year, result}, ...]}
      work/award-miss.json  未登録の受賞作
"""
import json, re, urllib.request, urllib.parse, pathlib, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
# 日本公開が大きく遅れた等で年ウィンドウを外れるが正しい対応
ALLOW = {("gone-with-the-wind", 1939), ("in-the-mood-for-love", 2001)}
WORK = ROOT / "work"
UA = {"User-Agent": "movie-db/1.0"}
CACHE = WORK / "wiki-cache"
CACHE.mkdir(parents=True, exist_ok=True)


def raw(title):
    f = CACHE / (re.sub(r"[^\w]", "_", title) + ".txt")
    if f.exists():
        return f.read_text("utf-8")
    u = "https://ja.wikipedia.org/w/index.php?title=%s&action=raw" % urllib.parse.quote(title)
    s = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8")
    f.write_text(s, "utf-8")
    return s


def link_titles(cell):
    cell = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", cell, flags=re.S)
    out = []
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", cell):
        out.append(m.group(2) or m.group(1))
    if not out:
        t = re.sub(r"<[^>]+>|\{\{[^}]*\}\}|'''|''", "", cell).strip()
        t = re.sub(r"^[『「]|[』」].*$", "", t).strip()
        if t:
            out.append(t)
    return out


def norm(t):
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"#.*$", "", t)
    t = re.sub(r"\s*\((?:19|20)\d\d年の?映画\)\s*$", "", t)
    t = re.sub(r"\s*\((?:映画|アニメ|小説|漫画|アニメ映画)\)\s*$", "", t)
    t = re.sub(r"[\s　・･:：!！?？'\"“”’、。,.\-‐−–—~〜/／\\|｜＆&+＋#＃*＊^%$@`()（）\[\]【】『』「」《》〈〉]", "", t)
    return t.lower()


def academy():
    s = raw("アカデミー作品賞")
    res = []
    for tbl in re.split(r"\n\{\|", s):
        cap = re.search(r"\|\+[^\n]*", tbl)
        if not cap:
            continue
        ym = re.search(r"((?:19|20)\d\d)", cap.group(0))
        if not ym:
            continue
        m = re.search(r'\|-\s*style="background:#FAEB86"\s*\n\|\s*([^\n]+)', tbl)
        if not m:
            continue
        ts = link_titles(m.group(1))
        if ts:
            res.append((int(ym.group(1)), ts[0], "作品賞"))
    return res


def palme():
    s = raw("パルム・ドール")
    res = []
    for line in s.splitlines():
        line = line.strip()
        m = re.match(r"\|\s*\[\[[^\]]*\|((?:19|20)\d\d)年\]\]\s*\|\|(.*)", line)
        if not m:
            m = re.match(r"\|\s*((?:19|20)\d\d)年\s*\|\|(.*)", line)
        if m:
            ts = link_titles(m.group(2).split("||")[0])
            if ts:
                res.append((int(m.group(1)), ts[0], "パルム・ドール"))
    return res


def japan_academy():
    s = raw("日本アカデミー賞")
    i = s.find("== 歴代受賞作品 ==")
    j = s.find("== 受賞辞退者 ==", i)
    s = s[i:j if j > 0 else len(s)]
    res = []
    for blk in re.split(r"\n\|-\n", s):
        ym = re.search(r"\[\[((?:19|20)\d\d)年\]\]", blk)
        if not ym or "最優秀作品賞" not in blk:
            continue
        tm = re.search(r"[『『]'''\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'''", blk)
        if tm:
            res.append((int(ym.group(1)), tm.group(2) or tm.group(1), "最優秀作品賞"))
    return res


def blue_ribbon():
    s = raw("ブルーリボン賞_(映画)")
    res = []
    cur = None
    for line in s.splitlines():
        t = line.strip()
        h = re.match(r"=+\s*第\s*(\d+)\s*回（((?:19|20)\d\d)年度?）", t)
        if h:
            cur = int(h.group(2))
            continue
        if cur and re.match(r"\*\s*作品賞", t):
            ts = link_titles(t)
            if ts:
                res.append((cur, ts[0], "作品賞"))
    return res


def kinema_junpo():
    s = raw("キネマ旬報")
    i = s.find("== 各年のベスト・テン結果 ==")
    j = s.find("== キネマ旬報読者賞 ==", i)
    s = s[i:j if j > 0 else len(s)]
    res = []
    cur = None
    mode = None
    rank = 0
    for line in s.splitlines():
        t = line.strip()
        h = re.match(r"=+\s*第\s*(\d+)\s*回（((?:19|20)\d\d)年度?）", t)
        if h:
            cur = int(h.group(2))
            mode = None
            continue
        if "読者選出" in t:
            mode = None
            continue
        if "'''日本映画ベスト・テン'''" in t:
            mode, rank = "日本映画", 0
            continue
        if "'''外国映画ベスト・テン'''" in t:
            mode, rank = "外国映画", 0
            continue
        if mode and cur:
            if t.startswith("#"):
                rank += 1
                if rank > 10:
                    mode = None
                    continue
                ts = link_titles(t[1:])
                if ts:
                    res.append((cur, ts[0], "%s 第%d位" % (mode, rank)))
            elif t:
                mode = None
    return res


EXTRACT = {
    "academy-awards": academy,
    "cannes": palme,
    "japan-academy": japan_academy,
    "blue-ribbon": blue_ribbon,
    "kinema-junpo": kinema_junpo,
}


def main():
    works = json.load(open(ROOT / "public/data/source/works.json", encoding="utf-8"))
    idx = {}
    for w in works:
        for key in (w["title"], w.get("originalTitle") or ""):
            if key:
                idx.setdefault(norm(key), []).append(w)
    hits, miss, far = {}, [], []
    for aid, fn in EXTRACT.items():
        got = fn()
        m = 0
        for year, title, result in got:
            cands = idx.get(norm(title))
            if not cands:
                miss.append({"awardId": aid, "year": year, "result": result, "title": title})
                continue
            best = min(cands, key=lambda w: abs(w["release"]["year"] - year))
            lag = best["release"]["year"] - year
            if -3 <= lag <= 4 or (best["id"], year) in ALLOW:
                hits.setdefault(best["id"], []).append({"awardId": aid, "year": year, "result": result})
                m += 1
            else:
                far.append({"awardId": aid, "year": year, "result": result, "title": title,
                            "workId": best["id"], "workYear": best["release"]["year"], "lag": lag})
        print("%s: 抽出%d 一致%d 保留%d 未登録%d" % (
            aid, len(got), m,
            len([x for x in far if x["awardId"] == aid]),
            len([x for x in miss if x["awardId"] == aid])))
    json.dump(far, open(WORK / "award-far.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(hits, open(WORK / "award-hits.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(miss, open(WORK / "award-miss.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("受賞歴を持つ作品:", len(hits), "  総受賞歴:", sum(len(v) for v in hits.values()))


if __name__ == "__main__":
    main()
