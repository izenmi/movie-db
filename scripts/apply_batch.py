#!/usr/bin/env python3
"""汎用バッチ反映スクリプト。
使い方: python3 scripts/apply_batch.py <batch.json>

batch.json の形式:
{
  "newStaff": [...],
  "newStudios": [...],
  "newActors": [...],
  "newThemes": [...],
  "newAwards": [...],
  "works": [...]
}

- 新規id(staff/studio/actor/theme/award)は既存と重複していればスキップ
- work は directorIds/screenwriterIds/studioIds/cast[].actorId/themeIds/
  awardResults[].awardId が(既存 + このバッチで追加される新規id)の中に存在するか検証し、
  存在しない参照があればその work 自体を反映せずレポートする
- directorIds/studioIds の空配列、region/medium/release/originalType の不正値も
  generate-manifest.mjs と同じルールで検証する
- 既存work idと重複するworkはスキップ(=同じbatch.jsonを二度applyしても増殖しない)

※ apply は1回だけ。実行前に既存idとの衝突件数をレポートで必ず確認すること。
"""
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "public" / "data" / "source"

REGIONS = {"japan", "overseas"}
MEDIUMS = {"liveaction", "animation"}
ORIGINAL_TYPES = {"manga", "lightnovel", "novel", "game", "original", "other"}

def load(name):
    with open(SRC / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)

def save(name, data):
    with open(SRC / f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def main():
    if len(sys.argv) != 2:
        print("usage: apply_batch.py <batch.json>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        batch = json.load(f)

    staff = load("staff")
    studios = load("studios")
    voice_actors = load("actors")
    themes = load("themes")
    awards = load("awards")
    works = load("works")

    staff_ids = {s["id"] for s in staff}
    studio_ids = {s["id"] for s in studios}
    va_ids = {v["id"] for v in voice_actors}
    theme_ids = {t["id"] for t in themes}
    award_ids = {a["id"] for a in awards}
    work_ids = {w["id"] for w in works}

    report = {"added": {}, "skipped_duplicates": {}, "rejected_works": []}

    def add_new(pool, id_set, key_name, kind):
        added, skipped = [], []
        for item in batch.get(key_name, []):
            if item["id"] in id_set:
                skipped.append(item["id"])
            else:
                pool.append(item)
                id_set.add(item["id"])
                added.append(item["id"])
        report["added"][kind] = added
        report["skipped_duplicates"][kind] = skipped

    add_new(staff, staff_ids, "newStaff", "staff")
    add_new(studios, studio_ids, "newStudios", "studios")
    add_new(voice_actors, va_ids, "newActors", "actors")
    add_new(themes, theme_ids, "newThemes", "themes")
    add_new(awards, award_ids, "newAwards", "awards")

    added_works = []
    for w in batch.get("works", []):
        if w["id"] in work_ids:
            report["rejected_works"].append({"id": w["id"], "reason": "duplicate work id"})
            continue

        missing = []
        if not w.get("directorIds"):
            missing.append("directorIds is empty")
        for sid in w.get("directorIds", []):
            if sid not in staff_ids:
                missing.append(f"directorId:{sid}")
        for sid in w.get("screenwriterIds", []):
            if sid not in staff_ids:
                missing.append(f"screenwriterId:{sid}")
        if not w.get("studioIds"):
            missing.append("studioIds is empty")
        for sid in w.get("studioIds", []):
            if sid not in studio_ids:
                missing.append(f"studioId:{sid}")
        for c in w.get("cast", []):
            if c.get("actorId") not in va_ids:
                missing.append(f"actorId:{c.get('actorId')}")
            if not c.get("character"):
                missing.append(f"cast entry {c.get('actorId')} missing character")
        for tid in w.get("themeIds", []):
            if tid not in theme_ids:
                missing.append(f"themeId:{tid}")
        for ar in w.get("awardResults", []):
            if ar.get("awardId") not in award_ids:
                missing.append(f"awardId:{ar.get('awardId')}")

        if w.get("region") not in REGIONS:
            missing.append(f"region must be japan/overseas (got {w.get('region')!r})")
        if w.get("medium") not in MEDIUMS:
            missing.append(f"medium must be liveaction/animation (got {w.get('medium')!r})")
        release = w.get("release") or {}
        month = release.get("month")
        if not isinstance(release.get("year"), int) or (
            month is not None and (not isinstance(month, int) or not 1 <= month <= 12)
        ):
            missing.append(f"release must be {{year, month?: 1-12}} (got {release!r})")
        runtime = w.get("runtime")
        if runtime is not None and (not isinstance(runtime, int) or runtime <= 0):
            missing.append(f"runtime must be a positive integer of minutes (got {runtime!r})")
        if w.get("originalType") not in ORIGINAL_TYPES:
            missing.append(f"originalType must be one of {sorted(ORIGINAL_TYPES)} (got {w.get('originalType')!r})")
        if len(w.get("cast", [])) > 5:
            missing.append("cast must list at most 5 main-cast entries")

        if missing:
            report["rejected_works"].append({"id": w["id"], "reason": f"invalid: {missing}"})
            continue

        works.append(w)
        work_ids.add(w["id"])
        added_works.append(w["id"])

    report["added"]["works"] = added_works

    save("staff", staff)
    save("studios", studios)
    save("actors", voice_actors)
    save("themes", themes)
    save("awards", awards)
    save("works", works)

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
