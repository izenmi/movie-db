#!/usr/bin/env python3
"""TMDbのカタログに「人気順で、まだworks.jsonに無い映画」を列挙させる。

**候補タイトルを自分で思いつくのはやめる**(姉妹サイト共通の教訓)。カタログ側に列挙させれば
出てくるものは全て実在し、重複も事前に除ける。anime-db の suggest_candidates.py (AniList版)
と同じ発想の TMDb 版。

使い方:
  python3 scripts/suggest_candidates.py out.txt [--pages 4] [--offset-page 1]
      [--lang ja] [--min-votes 200]

- sort_by: popularity.desc(TMDbユーザーの注目度順。日本国内の知名度と完全には一致しないが
  裏取り済みカタログとしては十分)
- --lang は original_language での絞り込み(ja=邦画、en=英語圏など。省略で全言語)
- --min-votes は vote_count.gte(低いとマイナー作品やノイズが混ざる)
- 1ページ20件。--offset-page を増やすと知名度の低い層に降りられる
- 出力: 邦題|tmdbId 形式(そのまま probe_tmdb.py に渡せる)。language=ja-JP の title は
  日本語ローカライズが無い作品だと原題のまま返るので、目視で邦題の有無を確認すること
- 重複判定はタイトル正規化一致とtmdbId一致の両方。最後の防波堤は apply_batch.py のid衝突検出
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from tmdb import SLEEP, get

SRC = Path(__file__).resolve().parent.parent / "public" / "data" / "source"


def norm(s: str) -> str:
    return re.sub(r"[\s　・･、。,，.!！?？:：;；~〜ー\-‐−『』「」【】()（）]", "",
                  unicodedata.normalize("NFKC", s or "")).lower()


def arg(name, default):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_path = Path(sys.argv[1])
    pages = int(arg("--pages", "4"))
    offset_page = int(arg("--offset-page", "1"))
    lang = arg("--lang", "")
    min_votes = int(arg("--min-votes", "200"))

    works = json.loads((SRC / "works.json").read_text(encoding="utf-8"))
    existing_titles = {norm(w["title"]) for w in works}
    existing_ids = {w.get("tmdbId") for w in works if w.get("tmdbId")}

    lines, seen = [], set()
    for page in range(offset_page, offset_page + pages):
        params = {"page": page, "sort_by": "popularity.desc", "vote_count.gte": min_votes,
                  "include_adult": "false"}
        if lang:
            params["with_original_language"] = lang
        data = get("/discover/movie", **params)
        results = data.get("results") or []
        for m in results:
            title = m.get("title") or m.get("original_title")
            if not title:
                continue
            key = norm(title)
            if key in seen or key in existing_titles or m["id"] in existing_ids:
                continue
            seen.add(key)
            lines.append(f"{title}|{m['id']}")
        print(f"page {page}: {len(results)} fetched, {len(lines)} new so far", flush=True)
        time.sleep(SLEEP)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(lines)} candidates)")


if __name__ == "__main__":
    main()
