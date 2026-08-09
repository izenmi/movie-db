#!/usr/bin/env python3
"""1000作品級の大量追加のための一括パイプライン(sweep → draft → finalize)。

TMDb から取れる機械的な情報(id・スタッフ・制作会社・キャスト・公開年月・上映時間・
ジャンル・ポスター)はすべて自動で埋め、**人間(=モデル)が書くしかない情報だけ**を
`*.todo.txt` に切り出す。埋めるべき情報は `*.fill.txt` に書いて finalize に渡す。
コンテキストに載るのは todo/fill だけなので、1作品あたりのトークン消費が最小になる。

  # 1) 候補プールを作る(何度でも追記できる。重複は自動で除外)
  python3 scripts/bulk.py sweep --pages 20 --min-votes 300
  python3 scripts/bulk.py sweep --pages 20 --lang ja --min-votes 30
  python3 scripts/bulk.py sweep --pages 10 --year-lte 1999 --min-votes 200

  # 2) 候補プールの先頭から N 件を裏取りしてドラフトを作る
  python3 scripts/bulk.py draft --tag b01 --n 25

  # 3) work/b01.todo.txt を読んで work/b01.fill.txt を書き、バッチJSONに変換する
  python3 scripts/bulk.py finalize --tag b01
  python3 scripts/apply_batch.py work/b01.batch.json

fill.txt の書式(区切りは半角パイプ。`-` は「変更なし/なし」):
  W|<slug>|<邦題 or ->|<titleKana or ->|<追加テーマ,カンマ区切り or ->|<originalType or ->|<seriesId or ->|<あらすじ150〜250字>
  C|<slug>|1:役名;2:役名;3:役名                      … キャストの役名を日本語にする
  P|<slug>|<表示名 or ->|<かな or ->                  … 新規スタッフ/キャストの日本語表記
  S|<slug>|<表示名 or =<既存studioId>>|<かな or ->    … 新規制作会社の日本語表記/既存への統合
  E|<seriesId>|<シリーズ名>|<かな>|<説明>             … 新規シリーズ
  R|<draft-slug>|<新しいslug>                         … 作品idの付け替え
  X|<slug>                                            … その作品をバッチから外す
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

from kana import has_japanese, is_katakana_name, kana_for_person, kana_for_title
from tmdb import get

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "data" / "source"
WORK = ROOT / "work"
TODAY = date.today().isoformat()

DIRECTOR_JOBS = {"Director"}
WRITER_JOBS = {"Screenplay", "Writer"}
ANIMATION_GENRE_ID = 16
MAX_CAST = 3
MAX_STUDIOS = 2

# TMDb ジャンルid → themes.json のテーマid(Animation/TV Movie は medium で表現するため無視)
GENRE_THEME = {
    28: "action", 12: "adventure", 35: "comedy", 80: "crime", 99: "documentary",
    18: "human-drama", 10751: "family", 14: "fantasy", 36: "history", 27: "horror",
    10402: "music", 9648: "mystery", 10749: "romance", 878: "sf", 53: "suspense",
    10752: "war", 37: "western",
}

# 除外する制作会社(製作委員会・出資のみ・配給専業など。CLAUDE.md のデータ方針に合わせる)
STUDIO_STOPWORDS = ("製作委員会", "Production Committee", "Partners", "Film Partners")


def norm(s: str) -> str:
    return re.sub(r"[\s　・･、。,，.!！?？:：;；~〜ー\-‐−『』「」【】()（）]", "",
                  unicodedata.normalize("NFKC", s or "")).lower()


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’]", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    if len(s) > 52:
        s = s[:52].rsplit("-", 1)[0]
    return s.strip("-")


def load(name):
    return json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))


def load_json(path, default):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- sweep
def cmd_sweep(args):
    WORK.mkdir(exist_ok=True)
    pool = load_json(WORK / "candidates.json", [])
    known = {c["id"] for c in pool}
    works = load("works")
    existing_titles = {norm(w["title"]) for w in works}
    existing_ids = {w.get("tmdbId") for w in works if w.get("tmdbId")}
    used = set(load_json(WORK / "used.json", []))

    added = 0
    for page in range(args.offset_page, args.offset_page + args.pages):
        params = {
            "page": page,
            "sort_by": args.sort,
            "vote_count.gte": args.min_votes,
            "include_adult": "false",
            "with_runtime.gte": 40,
        }
        if args.lang:
            params["with_original_language"] = args.lang
        if args.year_gte:
            params["primary_release_date.gte"] = f"{args.year_gte}-01-01"
        if args.year_lte:
            params["primary_release_date.lte"] = f"{args.year_lte}-12-31"
        if args.genre:
            params["with_genres"] = args.genre
        data = get("/discover/movie", **params)
        results = data.get("results") or []
        if not results:
            print(f"page {page}: empty, stop")
            break
        for m in results:
            title = m.get("title") or m.get("original_title") or ""
            if not title or m["id"] in known or m["id"] in existing_ids or m["id"] in used:
                continue
            if norm(title) in existing_titles:
                continue
            pool.append({
                "id": m["id"], "title": title,
                "lang": m.get("original_language"),
                "pop": round(m.get("popularity") or 0, 1),
                "date": m.get("release_date") or "",
                "votes": m.get("vote_count") or 0,
            })
            known.add(m["id"])
            added += 1
        print(f"page {page}: +{added} (pool {len(pool)})", flush=True)
        time.sleep(0.1)

    save_json(WORK / "candidates.json", pool)
    print(f"pool={len(pool)} added={added}")


# --------------------------------------------------------------------------- draft
class Resolver:
    """既存エンティティの再利用と新規エンティティのid採番。"""

    def __init__(self):
        self.pools = {}
        for kind, fname in (("staff", "staff"), ("actor", "actors"), ("studio", "studios")):
            items = load(fname)
            self.pools[kind] = {
                "ids": {x["id"] for x in items},
                "by_name": {norm(x["name"]): x["id"] for x in items},
            }
        self.cache = load_json(WORK / "entity-cache.json", {})
        self.aliases = load_json(WORK / "studio-aliases.json", {})
        self.pending = {"staff": {}, "actor": {}, "studio": {}}

    def save_cache(self):
        save_json(WORK / "entity-cache.json", self.cache)

    def person(self, pid, ja_name):
        key = f"p{pid}"
        hit = self.cache.get(key)
        if not hit:
            try:
                en = get(f"/person/{pid}", language="en-US").get("name") or ja_name
            except Exception:
                en = ja_name
            hit = {"ja": ja_name, "en": en}
            self.cache[key] = hit
            time.sleep(0.05)
        return hit

    def resolve_person(self, kind, pid, ja_name, role_note):
        info = self.person(pid, ja_name)
        ja, en = info["ja"], info["en"]
        pool = self.pools[kind]
        slug = slugify(en) or slugify(ja) or f"p{pid}"
        if slug in pool["ids"]:
            return slug, None
        if norm(ja) in pool["by_name"]:
            return pool["by_name"][norm(ja)], None
        if slug in self.pending[kind]:
            self.pending[kind][slug]["roles"].append(role_note)
            return slug, self.pending[kind][slug]
        entry = {"slug": slug, "ja": ja, "en": en, "tmdbId": pid,
                 "needJa": not has_japanese(ja), "roles": [role_note], "kind": kind}
        self.pending[kind][slug] = entry
        return slug, entry

    def resolve_studio(self, cid, name, role_note):
        pool = self.pools["studio"]
        if name in self.aliases:
            return self.aliases[name], None
        slug = slugify(name) or f"c{cid}"
        if slug in pool["ids"]:
            return slug, None
        if norm(name) in pool["by_name"]:
            return pool["by_name"][norm(name)], None
        if slug in self.pending["studio"]:
            self.pending["studio"][slug]["roles"].append(role_note)
            return slug, self.pending["studio"][slug]
        entry = {"slug": slug, "ja": name, "en": name, "tmdbId": cid,
                 "needJa": not has_japanese(name), "roles": [role_note], "kind": "studio"}
        self.pending["studio"][slug] = entry
        return slug, entry


def clean_character(ch: str) -> str:
    ch = re.sub(r"\((voice|uncredited|archive footage|singing voice)[^)]*\)", "", ch or "")
    ch = ch.split(" / ")[0]
    return ch.strip(" /")


def jp_release(detail):
    for entry in (detail.get("release_dates") or {}).get("results") or []:
        if entry.get("iso_3166_1") != "JP":
            continue
        dates = entry.get("release_dates") or []
        theatrical = [d for d in dates if d.get("type") in (2, 3)] or dates
        theatrical.sort(key=lambda d: d.get("release_date") or "9999")
        if theatrical and theatrical[0].get("release_date"):
            iso = theatrical[0]["release_date"]
            return {"year": int(iso[0:4]), "month": int(iso[5:7])}
    return None


def cmd_draft(args):
    WORK.mkdir(exist_ok=True)
    pool = load_json(WORK / "candidates.json", [])
    used = set(load_json(WORK / "used.json", []))
    works = load("works")
    existing_titles = {norm(w["title"]) for w in works}
    existing_ids = {w.get("tmdbId") for w in works if w.get("tmdbId")}
    work_ids = {w["id"] for w in works}
    res = Resolver()

    picked, todo_lines, drafts = 0, [], []
    for cand in pool:
        if picked >= args.n:
            break
        cid = cand["id"]
        if cid in used or cid in existing_ids:
            continue
        if args.lang and cand.get("lang") != args.lang:
            continue
        used.add(cid)
        try:
            d = get(f"/movie/{cid}", append_to_response="credits,release_dates")
        except Exception as e:
            print(f"ERR {cand['title']}: {e}", flush=True)
            continue
        title = d.get("title") or d.get("original_title") or ""
        orig_lang0 = d.get("original_language")
        if norm(title) in existing_titles:
            print(f"DUP {title}", flush=True)
            continue
        overview = (d.get("overview") or "").strip()
        if not overview:
            print(f"SKIP {title} (no ja overview)", flush=True)
            continue
        if (not has_japanese(title) and orig_lang0 != "ja"
                and norm(title) == norm(d.get("original_title") or "")):
            print(f"SKIP {title} (邦題なし)", flush=True)
            continue
        runtime = d.get("runtime") or 0
        if runtime < 40:
            print(f"SKIP {title} (runtime {runtime})", flush=True)
            continue

        credits = d.get("credits") or {}
        crew = credits.get("crew") or []
        directors = [c for c in crew if c.get("job") in DIRECTOR_JOBS]
        writers = ([c for c in crew if c.get("job") == "Screenplay"]
                   or [c for c in crew if c.get("job") in WRITER_JOBS])[:2]
        companies = [c for c in (d.get("production_companies") or [])
                     if not any(w in (c.get("name") or "") for w in STUDIO_STOPWORDS)]
        if not directors or not companies:
            print(f"SKIP {title} (no director/company)", flush=True)
            continue

        orig_lang = orig_lang0
        region = "japan" if orig_lang == "ja" else "overseas"
        genre_ids = [g["id"] for g in d.get("genres") or []]
        medium = "animation" if ANIMATION_GENRE_ID in genre_ids else "liveaction"

        # 作品slug: 英語圏はoriginal_title、それ以外はen-USの題名から
        base = d.get("original_title") if orig_lang == "en" else ""
        if not base or has_japanese(base):
            try:
                base = get(f"/movie/{cid}", language="en-US").get("title") or ""
                time.sleep(0.05)
            except Exception:
                base = ""
        slug = slugify(base)
        if not slug or has_japanese(base):
            slug = f"w{cid}"
        if slug in work_ids or any(x["work"]["id"] == slug for x in drafts):
            yr = (d.get("release_date") or "")[:4]
            slug = f"{slug}-{yr}" if yr else f"{slug}-{cid}"
        work_ids.add(slug)

        seen_staff = []
        director_ids = []
        for c in directors[:2]:
            sid, _ = res.resolve_person("staff", c["id"], c.get("name") or "", f"『{title}』監督")
            if sid not in director_ids:
                director_ids.append(sid)
                seen_staff.append(sid)
        writer_ids = []
        for c in writers:
            sid, _ = res.resolve_person("staff", c["id"], c.get("name") or "", f"『{title}』脚本")
            if sid not in writer_ids:
                writer_ids.append(sid)
        writer_ids = [w for w in writer_ids if w not in director_ids] or []

        studio_ids = []
        for c in companies[:MAX_STUDIOS]:
            sid, _ = res.resolve_studio(c["id"], c.get("name") or "", f"『{title}』製作")
            if sid not in studio_ids:
                studio_ids.append(sid)

        cast = []
        for c in (credits.get("cast") or [])[:MAX_CAST]:
            aid, _ = res.resolve_person("actor", c["id"], c.get("name") or "", f"『{title}』出演")
            if any(x["actorId"] == aid for x in cast):
                continue
            cast.append({"actorId": aid, "character": clean_character(c.get("character") or "")})

        jp = jp_release(d)
        rel_iso = d.get("release_date") or ""
        if jp:
            release, rel_note = jp, ""
        elif rel_iso:
            release = {"year": int(rel_iso[:4]), "month": int(rel_iso[5:7])}
            rel_note = "日本公開日が確認できないため本国公開年月を採用。"
        else:
            print(f"SKIP {title} (no release date)", flush=True)
            continue

        themes = []
        for g in genre_ids:
            t = GENRE_THEME.get(g)
            if t and t not in themes:
                themes.append(t)

        work = {
            "id": slug,
            "title": title,
            "titleKana": kana_for_title(title),
            "directorIds": director_ids,
            "screenwriterIds": writer_ids,
            "studioIds": studio_ids,
            "cast": cast,
            "themeIds": themes,
            "region": region,
            "medium": medium,
            "release": release,
            "runtime": runtime,
            "originalType": "original",
            "synopsis": "",
            "tmdbId": cid,
            "externalLinks": {},
            "sourceNote": f"TMDb(ja-JP)で裏取り({TODAY})。{rel_note}",
            "updatedAt": TODAY,
        }
        ot = d.get("original_title") or ""
        if ot and norm(ot) != norm(title):
            work["originalTitle"] = ot

        drafts.append({"work": work, "genres": [g["name"] for g in d.get("genres") or []],
                       "overview": overview[:120],
                       "castNames": [(c.get("name"), c.get("character")) for c in (credits.get("cast") or [])[:MAX_CAST]]})
        picked += 1
        time.sleep(0.05)

    res.save_cache()
    save_json(WORK / "used.json", sorted(used))

    # todo.txt(モデルが読む唯一のファイル。1作品5〜7行に収める)
    def mark(kind, sid):
        p = res.pending[kind].get(sid)
        if p and p["needJa"]:
            return f"*{sid}[{p['en']}]"
        if p:
            return f"+{sid}"
        return sid

    for i, dr in enumerate(drafts, 1):
        w = dr["work"]
        rel = w["release"]
        head = (f"#{i} {w['id']}|{w['title']}|{w.get('originalTitle','-')}|"
                f"{rel['year']}.{rel.get('month','?')}|{w['runtime']}m|"
                f"{'邦' if w['region']=='japan' else '海'}{'ア' if w['medium']=='animation' else '実'}|"
                f"kana:{w['titleKana'] or '?'}")
        todo_lines.append(head)
        todo_lines.append(" T:" + (",".join(w["themeIds"]) or "-") + "  G:" + ",".join(dr["genres"]))
        todo_lines.append(" D:" + ",".join(mark("staff", s) for s in w["directorIds"]) +
                          ("  W:" + ",".join(mark("staff", s) for s in w["screenwriterIds"]) if w["screenwriterIds"] else "") +
                          "  S:" + ",".join(mark("studio", s) for s in w["studioIds"]))
        cast_parts = []
        for n, c in enumerate(w["cast"], 1):
            cast_parts.append(f"{n}:{mark('actor', c['actorId'])}/{c['character'] or '?'}")
        if cast_parts:
            todo_lines.append(" A:" + " ".join(cast_parts))
        if dr["overview"]:
            todo_lines.append(" O:" + dr["overview"].replace("\n", " "))

    (WORK / f"{args.tag}.draft.json").write_text(
        json.dumps({"tag": args.tag, "drafts": drafts,
                    "pending": res.pending}, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / f"{args.tag}.todo.txt").write_text("\n".join(todo_lines) + "\n", encoding="utf-8")
    n_new = sum(len(v) for v in res.pending.values())
    print(f"drafted {len(drafts)} works, {n_new} new entities -> work/{args.tag}.todo.txt")


# --------------------------------------------------------------------------- finalize
LATIN_RUN = re.compile(r"[A-Za-z]{4,}")
BAD_CHARS = re.compile(r"[Ѐ-ӿ가-힯]")


def cmd_finalize(args):
    draft = json.loads((WORK / f"{args.tag}.draft.json").read_text(encoding="utf-8"))
    fill_path = WORK / f"{args.tag}.fill.txt"
    lines = fill_path.read_text(encoding="utf-8").splitlines()

    W, C, P, S, E, R, X, N = {}, {}, {}, {}, [], {}, set(), set()
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        f = [x.strip() for x in ln.split("|")]
        kind = f[0]
        if kind == "W":
            W[f[1]] = f[2:]
        elif kind == "C":
            C[f[1]] = f[2]
        elif kind == "P":
            P[f[1]] = f[2:]
        elif kind == "S":
            S[f[1]] = f[2:]
        elif kind == "E":
            E.append(f[1:])
        elif kind == "R":
            R[f[1]] = f[2]
        elif kind == "X":
            X.add(f[1])
        elif kind == "N":
            N.add(f[1])

    pending = draft["pending"]
    aliases = load_json(WORK / "studio-aliases.json", {})
    problems = []

    # --- 制作会社: 既存への統合(=id)か、日本語表記の指定
    studio_remap = {}
    for slug, entry in list(pending["studio"].items()):
        fill = S.get(slug)
        if fill and fill[0].startswith("="):
            target = fill[0][1:]
            studio_remap[slug] = target
            aliases[entry["en"]] = target
            pending["studio"].pop(slug)
            continue
        if fill and fill[0] != "-":
            entry["ja"] = fill[0]
            aliases[entry["en"]] = slug
        elif entry["needJa"]:
            problems.append(f"studio {slug} の日本語表記が未指定 ({entry['en']})")
        if fill and len(fill) > 1 and fill[1] != "-":
            entry["kana"] = fill[1]

    for kind in ("staff", "actor"):
        for slug, entry in pending[kind].items():
            fill = P.get(slug)
            if fill and fill[0] != "-":
                entry["ja"] = fill[0]
            elif entry["needJa"]:
                problems.append(f"{kind} {slug} の日本語表記が未指定 ({entry['en']})")
            if fill and len(fill) > 1 and fill[1] != "-":
                entry["kana"] = fill[1]

    def build_entity(entry, kind):
        name = entry["ja"]
        kana = entry.get("kana") or kana_for_person(name, entry["en"])
        roles = entry["roles"]
        first = roles[0].split("』")[0].replace("『", "")
        if kind == "staff":
            jobs = {r.split("』")[1] for r in roles}
            if jobs == {"監督"}:
                desc = f"映画監督。『{first}』などを監督した。"
            elif jobs == {"脚本"}:
                desc = f"脚本家。『{first}』などの脚本を手がけた。"
            else:
                desc = f"映画監督・脚本家。『{first}』などの監督・脚本を手がけた。"
        elif kind == "actor":
            desc = f"俳優。『{first}』などに出演。"
        else:
            desc = f"映画製作会社。『{first}』などを製作した。"
        note = f"TMDb(ja-JP)で裏取り({TODAY})。"
        if entry["en"] and entry["en"] != name:
            note += f"TMDb表記: {entry['en']}。"
        return {"id": entry["slug"], "name": name, "nameKana": kana,
                "description": desc, "externalLinks": {}, "sourceNote": note,
                "updatedAt": TODAY}

    batch = {
        "newStaff": [build_entity(e, "staff") for e in pending["staff"].values()],
        "newActors": [build_entity(e, "actor") for e in pending["actor"].values()],
        "newStudios": [build_entity(e, "studio") for e in pending["studio"].values()],
        "newSeries": [{"id": e[0], "name": e[1], "nameKana": e[2], "description": e[3],
                       "externalLinks": {}, "sourceNote": f"Wikipedia日本語版で裏取り({TODAY})。",
                       "updatedAt": TODAY} for e in E],
        "newThemes": [],
        "works": [],
    }

    known_themes = {t["id"] for t in load("themes")}
    for dr in draft["drafts"]:
        w = dr["work"]
        slug = w["id"]
        if slug in X:
            continue
        fill = W.get(slug)
        if not fill:
            problems.append(f"work {slug} の W 行がない")
            continue
        title, kana, extra_themes, otype, series, synopsis = (fill + ["-"] * 6)[:6]
        if title != "-":
            w["title"] = title
        if kana != "-":
            w["titleKana"] = kana
        if not w["titleKana"]:
            problems.append(f"work {slug} の titleKana がない")
        if extra_themes != "-":
            for t in extra_themes.split(","):
                t = t.strip()
                if not t:
                    continue
                if t not in known_themes:
                    problems.append(f"work {slug} の未知テーマ {t}")
                elif t not in w["themeIds"]:
                    w["themeIds"].append(t)
        if slug in N:
            w["screenwriterIds"] = []
        if otype != "-":
            w["originalType"] = otype
        if series != "-":
            w["seriesId"] = series
        if synopsis == "-" or not synopsis:
            problems.append(f"work {slug} のあらすじがない")
        else:
            w["synopsis"] = synopsis
            n = len(synopsis)
            if not 130 <= n <= 280:
                problems.append(f"work {slug} のあらすじが{n}字")
            if LATIN_RUN.search(synopsis) or BAD_CHARS.search(synopsis):
                problems.append(f"work {slug} のあらすじに非日本語表記")
        if slug in R:
            w["id"] = R[slug]
        # キャスト役名
        if slug in C and C[slug] != "-":
            for part in C[slug].split(";"):
                if ":" not in part:
                    continue
                idx, name_ja = part.split(":", 1)
                try:
                    i = int(idx.strip()) - 1
                except ValueError:
                    continue
                if 0 <= i < len(w["cast"]):
                    w["cast"][i]["character"] = name_ja.strip()
        w["cast"] = [c for c in w["cast"] if c["character"] and c["character"] != "?"]
        for c in w["cast"]:
            if LATIN_RUN.search(c["character"]):
                problems.append(f"work {w['id']} の役名が英語のまま: {c['character']}")
        w["studioIds"] = [studio_remap.get(s, s) for s in w["studioIds"]]
        seen = set()
        w["studioIds"] = [s for s in w["studioIds"] if not (s in seen or seen.add(s))]
        if not w["themeIds"]:
            problems.append(f"work {w['id']} にテーマがない")
        batch["works"].append(w)

    used_ids = set()
    for w in batch["works"]:
        used_ids |= set(w["directorIds"]) | set(w["screenwriterIds"]) | set(w["studioIds"])
        used_ids |= {c["actorId"] for c in w["cast"]}
    for key in ("newStaff", "newActors", "newStudios"):
        batch[key] = [e for e in batch[key] if e["id"] in used_ids]
    problems[:] = [p for p in problems
                   if not re.match(r"^(staff|actor|studio) (\S+) ", p)
                   or re.match(r"^(staff|actor|studio) (\S+) ", p).group(2) in used_ids]

    save_json(WORK / "studio-aliases.json", aliases)
    out = WORK / f"{args.tag}.batch.json"
    out.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"works={len(batch['works'])} staff={len(batch['newStaff'])} "
          f"actors={len(batch['newActors'])} studios={len(batch['newStudios'])} "
          f"series={len(batch['newSeries'])} -> {out}")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sw = sub.add_parser("sweep")
    sw.add_argument("--pages", type=int, default=10)
    sw.add_argument("--offset-page", type=int, default=1)
    sw.add_argument("--lang", default="")
    sw.add_argument("--min-votes", type=int, default=200)
    sw.add_argument("--sort", default="popularity.desc")
    sw.add_argument("--year-gte", type=int)
    sw.add_argument("--year-lte", type=int)
    sw.add_argument("--genre", default="")
    sw.set_defaults(func=cmd_sweep)

    dr = sub.add_parser("draft")
    dr.add_argument("--tag", required=True)
    dr.add_argument("--n", type=int, default=25)
    dr.add_argument("--lang", default="")
    dr.set_defaults(func=cmd_draft)

    fi = sub.add_parser("finalize")
    fi.add_argument("--tag", required=True)
    fi.set_defaults(func=cmd_finalize)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
