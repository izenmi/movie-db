// TMDbからポスター画像(poster_path)を取得して public/data/source/covers-cache.json に
// 保存する。works.json の各エントリが持つ tmdbId をキーに /movie/{id} を直接引くので、
// 姉妹サイトのタイトル検索ベースの表紙取得と違い「あいまいマッチの誤ヒット」が構造的に起きない
// (tmdbId の登録間違いはその限りではないので、matchedTitle の目視確認は省略しないこと)。
//
// 使い方:
//   node scripts/fetch-covers.mjs [--only=id1,id2] [--force] [--retry-misses]
//
// - 認証: scripts/.tmdb-token(gitignore対象)か環境変数 TMDB_TOKEN の Bearer トークン。
//   APIコールにだけ必要で、画像CDN(image.tmdb.org)へのホットリンク自体は認証不要
// - 既定ではキャッシュに無い作品だけ取得する
// - --retry-misses は coverUrl:null のエントリだけを再試行する
// - --force は既存エントリも再取得するが、再取得に失敗した場合は既存の値を維持する([keep])
// - 画像は content-type と実バイト数で検証する(content-length ヘッダはHTTP/2で
//   返らないことがあるため使わない — game-db の IGDB 実装で踏んだバグ)
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const rootDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const sourceDir = path.join(rootDir, "public", "data", "source");
const cachePath = path.join(sourceDir, "covers-cache.json");
const tokenPath = path.join(rootDir, "scripts", ".tmdb-token");

const API = "https://api.themoviedb.org/3";
// w500 はカード表示(~200px)にもRetinaにも足りる幅。オリジナルはファイルが大きすぎる。
const IMAGE_BASE = "https://image.tmdb.org/t/p/w500";
const SLEEP_MS = 300;

const token =
  process.env.TMDB_TOKEN?.trim() || (existsSync(tokenPath) ? readFileSync(tokenPath, "utf-8").trim() : "");
if (!token) {
  console.error("TMDb token not found. Put the API Read Access Token in scripts/.tmdb-token or set TMDB_TOKEN.");
  process.exit(1);
}

const args = process.argv.slice(2);
const force = args.includes("--force");
const retryMisses = args.includes("--retry-misses");
const onlyArg = args.find((a) => a.startsWith("--only="));
const only = onlyArg ? new Set(onlyArg.slice("--only=".length).split(",")) : null;

const works = JSON.parse(readFileSync(path.join(sourceDir, "works.json"), "utf-8"));
const cache = existsSync(cachePath) ? JSON.parse(readFileSync(cachePath, "utf-8")) : {};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function queryMovie(tmdbId) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(`${API}/movie/${tmdbId}?language=ja-JP`, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "User-Agent": "movie-db-fan-site/0.1 (https://izenmi.github.io/movie-db/)",
      },
    });
    if (res.status === 429) {
      const wait = Number(res.headers.get("retry-after") ?? 5);
      console.log(`  429 rate limited, waiting ${wait}s...`);
      await sleep((wait + 1) * 1000);
      continue;
    }
    if (!res.ok) throw new Error(`TMDb HTTP ${res.status}`);
    return res.json();
  }
  throw new Error("rate limited repeatedly");
}

async function verifyImage(url) {
  const res = await fetch(url);
  if (!res.ok) return false;
  const type = res.headers.get("content-type") ?? "";
  if (!type.startsWith("image/")) return false;
  const buf = await res.arrayBuffer();
  return buf.byteLength > 1000;
}

function shouldFetch(w) {
  if (only && !only.has(w.id)) return false;
  const entry = cache[w.id];
  if (!entry) return true;
  if (retryMisses) return entry.coverUrl == null;
  return force;
}

const targets = works.filter((w) => shouldFetch(w));
console.log(`fetch-covers: ${targets.length} works to process (of ${works.length} total)`);

let ok = 0;
let miss = 0;
let kept = 0;
for (const w of targets) {
  if (!w.tmdbId) {
    // tmdbId が無い作品は取得できない。probe_tmdb.py で id を確認して works.json に入れること。
    if (!cache[w.id]) cache[w.id] = { coverUrl: null, note: "tmdbId未設定のため未取得" };
    console.log(`[skip] ${w.title}: tmdbId not set`);
    miss++;
    continue;
  }
  try {
    const movie = await queryMovie(w.tmdbId);
    const url = movie?.poster_path ? `${IMAGE_BASE}${movie.poster_path}` : null;
    if (url && (await verifyImage(url))) {
      cache[w.id] = {
        coverUrl: url,
        matchedTitle: movie.title ?? movie.original_title ?? null,
        tmdbId: w.tmdbId,
      };
      console.log(`[ok]   ${w.title} -> ${cache[w.id].matchedTitle}`);
      ok++;
    } else if (cache[w.id]?.coverUrl) {
      console.log(`[keep] ${w.title}: refetch failed, keeping existing cover`);
      kept++;
    } else {
      cache[w.id] = { coverUrl: null, tmdbId: w.tmdbId, note: "TMDbに画像なし/検証失敗" };
      console.log(`[miss] ${w.title}`);
      miss++;
    }
  } catch (e) {
    if (cache[w.id]?.coverUrl) {
      console.log(`[keep] ${w.title}: ${e.message}`);
      kept++;
    } else {
      cache[w.id] = { coverUrl: null, tmdbId: w.tmdbId ?? null, note: `取得エラー: ${e.message}` };
      console.log(`[err]  ${w.title}: ${e.message}`);
      miss++;
    }
  }
  await sleep(SLEEP_MS);
}

writeFileSync(cachePath, JSON.stringify(cache, null, 2) + "\n", "utf-8");
console.log(`fetch-covers: done. ok=${ok} miss=${miss} keep=${kept} -> ${cachePath}`);
