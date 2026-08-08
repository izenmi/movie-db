#!/usr/bin/env python3
"""TMDbで候補映画を一括裏取りする主力ツール。

使い方:
  python3 scripts/probe_tmdb.py candidates.txt [--out probe.json]

candidates.txt は1行1候補:
  タイトル              … TMDbを日本語タイトルで検索
  タイトル|12345        … TMDb id直指定(検索の誤マッチを避けたいとき)

- **works.json との重複判定を検索の前に行い、DUP と出た候補はネットワークアクセスしない**
  (タイトルの正規化一致 or tmdbId の一致)
- 1候補につき /movie/{id}?append_to_response=credits,release_dates を1リクエストで取る
  (検索経由の場合は+1リクエスト)
- 出力(JSON配列)の各要素:
  q / status(OK|DUP|MISS) / id / title(邦題) / originalTitle / originalLanguage /
  regionGuess(japan|overseas) / animation(bool) / jpRelease({year,month}|null。
  release_datesのJP劇場公開日) / releaseDate(本国) / runtime / genres /
  studios(production_companies名の配列) / directors / screenwriters /
  cast([{char, actor}] 最大6) / poster / popularity / overview(先頭200字)
- **海外作品の人名は英語表記で返る**。登録時は日本で流通しているカタカナ表記に直し、
  sourceNote に TMDb 表記を書き残すこと
- statusがOKでも **title が候補とずれていないか必ず目視すること**(同名のリメイク・
  続編を拾うことがある)
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from tmdb import SLEEP, get

SRC = Path(__file__).resolve().parent.parent / "public" / "data" / "source"

ANIMATION_GENRE_ID = 16
DIRECTOR_JOBS = {"Director"}
WRITER_JOBS = {"Screenplay", "Writer"}


def norm(s: str) -> str:
    return re.sub(r"[\s　・･、。,，.!！?？:：;；~〜ー\-‐−『』「」【】()（）]", "",
                  unicodedata.normalize("NFKC", s or "")).lower()


def pick_result(results, target):
    """検索結果から title/original_title が候補に最も近いものを選ぶ。"""
    tn = norm(target)
    best, best_score = None, -10000
    for m in results:
        title = norm(m.get("title") or "")
        original = norm(m.get("original_title") or "")
        if tn and (tn == title or tn == original):
            score = 100
        elif tn and (tn in title or title in tn):
            score = 50 - abs(len(title) - len(tn))
        else:
            score = 0 - abs(len(title) - len(tn))
        # 同点なら人気の高い方(リメイクの誤マッチをやや抑える)
        score += min((m.get("popularity") or 0) / 1000, 0.5)
        if score > best_score:
            best, best_score = m, score
    return best


def jp_release(detail):
    """release_dates から日本の劇場公開日({year, month})を引く。無ければ None。"""
    for entry in (detail.get("release_dates") or {}).get("results") or []:
        if entry.get("iso_3166_1") != "JP":
            continue
        dates = entry.get("release_dates") or []
        # type 3=Theatrical, 2=Theatrical (limited) を優先し、無ければ最初の日付
        theatrical = [d for d in dates if d.get("type") in (2, 3)] or dates
        theatrical.sort(key=lambda d: d.get("release_date") or "9999")
        if theatrical and theatrical[0].get("release_date"):
            iso = theatrical[0]["release_date"]
            return {"year": int(iso[0:4]), "month": int(iso[5:7])}
    return None


def summarize(q, detail):
    credits = detail.get("credits") or {}
    directors, writers = [], []
    for c in credits.get("crew") or []:
        if c.get("job") in DIRECTOR_JOBS:
            directors.append(c.get("name"))
        elif c.get("job") in WRITER_JOBS:
            writers.append(c.get("name"))
    cast = [{"char": c.get("character") or "", "actor": c.get("name")}
            for c in (credits.get("cast") or [])[:6]]
    genres = [g["name"] for g in detail.get("genres") or []]
    genre_ids = {g["id"] for g in detail.get("genres") or []}
    return {
        "q": q,
        "status": "OK",
        "id": detail["id"],
        "title": detail.get("title"),
        "originalTitle": detail.get("original_title"),
        "originalLanguage": detail.get("original_language"),
        "regionGuess": "japan" if detail.get("original_language") == "ja" else "overseas",
        "animation": ANIMATION_GENRE_ID in genre_ids,
        "jpRelease": jp_release(detail),
        "releaseDate": detail.get("release_date"),
        "runtime": detail.get("runtime"),
        "genres": genres,
        "studios": [c["name"] for c in detail.get("production_companies") or []],
        "directors": directors,
        "screenwriters": writers,
        "cast": cast,
        "poster": detail.get("poster_path"),
        "popularity": detail.get("popularity"),
        "overview": (detail.get("overview") or "")[:200],
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_path = None
    if "--out" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--out") + 1])

    works = json.loads((SRC / "works.json").read_text(encoding="utf-8"))
    existing_titles = {norm(w["title"]) for w in works}
    existing_ids = {w.get("tmdbId") for w in works if w.get("tmdbId")}

    lines = [ln.strip() for ln in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()]
    results = []
    for ln in lines:
        if not ln or ln.startswith("#"):
            continue
        title, _, id_part = ln.partition("|")
        title = title.strip()
        tmdb_id = int(id_part) if id_part.strip().isdigit() else None

        if norm(title) in existing_titles or (tmdb_id and tmdb_id in existing_ids):
            results.append({"q": ln, "status": "DUP"})
            print(f"DUP  {title}", flush=True)
            continue

        try:
            if not tmdb_id:
                found = get("/search/movie", query=title, include_adult="false")
                best = pick_result(found.get("results") or [], title)
                if not best:
                    results.append({"q": ln, "status": "MISS"})
                    print(f"MISS {title}", flush=True)
                    time.sleep(SLEEP)
                    continue
                tmdb_id = best["id"]
                if tmdb_id in existing_ids:
                    results.append({"q": ln, "status": "DUP"})
                    print(f"DUP  {title} (tmdbId {tmdb_id})", flush=True)
                    time.sleep(SLEEP)
                    continue
                time.sleep(SLEEP)
            detail = get(f"/movie/{tmdb_id}", append_to_response="credits,release_dates")
        except Exception as e:
            results.append({"q": ln, "status": "MISS", "error": str(e)})
            print(f"ERR  {title}: {e}", flush=True)
            time.sleep(SLEEP)
            continue

        r = summarize(ln, detail)
        results.append(r)
        jp = r["jpRelease"]
        print(
            f"OK   {title} -> {r['title']} ({r['originalTitle']}, "
            f"JP:{jp['year'] if jp else '?'}, {r['runtime']}min, "
            f"監督:{'/'.join(filter(None, r['directors']))})",
            flush=True,
        )
        time.sleep(SLEEP)

    if out_path:
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {out_path} ({len(results)} entries)")


if __name__ == "__main__":
    main()
