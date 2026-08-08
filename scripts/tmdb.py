#!/usr/bin/env python3
"""TMDb API v3 の薄い共有ラッパ(probe_tmdb.py / suggest_candidates.py が使う)。

- エンドポイント: https://api.themoviedb.org/3
- 認証: Bearer トークン(API Read Access Token)。scripts/.tmdb-token(gitignore対象)か
  環境変数 TMDB_TOKEN から読む。トークンはリポジトリに絶対にコミットしないこと。
- レート制限: 公式には約50req/秒まで許容だが、行儀よく既定0.3秒スリープを挟む。
  429が返ったら Retry-After を尊重して再試行する。
- language=ja-JP を既定で付ける(邦題・日本語あらすじ優先。無い作品は原語にフォールバック)。
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.themoviedb.org/3"
SLEEP = 0.3
TOKEN_PATH = Path(__file__).resolve().parent / ".tmdb-token"


def token() -> str:
    t = os.environ.get("TMDB_TOKEN", "").strip()
    if not t and TOKEN_PATH.exists():
        t = TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not t:
        raise SystemExit(
            "TMDb token not found. Put the API Read Access Token in scripts/.tmdb-token "
            "or set TMDB_TOKEN."
        )
    return t


def get(path: str, retries: int = 3, **params) -> dict:
    params.setdefault("language", "ja-JP")
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token()}",
                "User-Agent": "movie-db-fan-site/0.1 (https://izenmi.github.io/movie-db/)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = int(e.headers.get("Retry-After") or 5)
                print(f"  429 rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait + 1)
                continue
            raise
    raise RuntimeError("unreachable")
