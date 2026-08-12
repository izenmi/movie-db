# movie-db

邦画・洋画・アニメ映画を制作会社・監督・脚本・キャスト・公開年・受賞歴・テーマから検索できるファンデータベース。**年表(/timeline)機能はユーザー指示で2026-08-09に削除済み(再提案しない)**。姉妹サイト7番目(2026-08-08作成)。scaffoldのコピー元は**anime-db**(非書籍・キーアート表紙・スタッフ/キャスト構造が最も近く改造距離が最短だったため)。アーキテクチャ・デザインシステム・運用ノウハウはranobe-db系列をそのまま踏襲している。

- 公開URL: https://izenmi.github.io/movie-db/
- リポジトリ: `izenmi/movie-db`(public。GitHub Pagesは無料枠だとpublicでないと使えない)
- スタック: React 18 + TypeScript + Vite 5 + `react-router-dom`(`BrowserRouter`)

## データモデル上の判断(このサイト固有・最重要)

- **映画1本で1エントリ**。続編・リメイクは別エントリで、シリーズは`series.json`のエンティティ(作品から`seriesId`で任意参照。2026-08-09にエンティティ化)。`/series`に一覧・詳細ページ(**一覧は収録作品数の多い順、詳細内の作品は新しい順**で固定)、ナビタブと作品一覧の絞り込みもある。細かい展開の注記は`seriesNote`(自由記述)
- **`region: japan|overseas`(邦画/海外)と`medium: liveaction|animation`(実写/アニメ)の2軸**が絞り込みの柱。合作は主たる製作国で決めてsourceNoteに明記
- **アニメ映画はanime-db(単独劇場アニメのみ収録)と重複してよい**とユーザーが明示的に決定済み。重複作品は`relatedAnimeUrl`で相互リンクする(姉妹サイトリンクは5方向: novel/comic/mystery/game/anime)
- **`release: { year, month? }` は日本公開を基本**とし、判別が難しい作品は本国公開年+sourceNote明記。monthは裏取りできたときだけ
- **`title`は邦題、`originalTitle`は原題**(邦題と同じ邦画では省略)。パラサイトの原題は기생충のようにハングル等もそのまま入れる(あらすじには非日本語文字を入れない)
- **スタッフは単一ファイル2ロール方式**: `staff.json`を`directorIds`(必須≥1)と`screenwriterIds`(任意。監督兼任のみなら空)の両方から参照する(anime-dbの監督/シリーズ構成と同じ設計)
- **`studioIds`(制作会社)は必須≥1**。クレジット上の製作会社を最大2社程度登録し、製作委員会・出資のみの会社は登録しない
- **キャストは各作品の主要キャスト最大5名まで**(`cast: [{actorId, character}]`、役名必須)。apply_batch.pyが6名以上を拒否する。シード時は3名/作品に抑えた。キャスト詳細ページは役名つき出演一覧(公開順固定)
- **`runtime`は上映時間(分)**。`status`(放送状態)や`episodes`は映画に不要なので撤去した
- spoilerタグ機構はそのまま維持(現状「どんでん返し」1タグのみspoiler)。レコメンドのスコア計算からも除外される

## データフロー(source → generated)

- `public/data/source/*.json` … 一次データ(works/staff/studios/actors/themes/awards + covers-cache)
- `public/data/generated/*.json` … `scripts/generate-manifest.mjs`が生成(`.gitignore`対象)
- 生成スクリプトの検証(失敗するとビルドが落ちる): 全id参照整合 / `directorIds`・`studioIds`空配列不可 / `region`・`medium`・`originalType`のenum検証 / `release.month`は1-12 / cast役名必須

### 転送量の設計(2026-08-12。**作品をフル展開して埋め込まない**)

スタッフ・制作会社・キャスト・シリーズ・テーマの各生成ファイルは作品を **id** で持ち
(`workIds` / `directedWorkIds` / `writtenWorkIds` / `roles[].workId`)、表示側は
`getWorksByIds()`(works.json の取得済みキャッシュ)から引き直す。
あらすじと出典メモは作品詳細でしか使わないので **`work-texts.json`** に分けてある。

以前は作品をフル展開して埋め込んでいたため `themes.json` が gzip 4.5MB・`actors.json` が 3.3MB あり、
トップページだけで gzip 5.8MB を転送していた。現在は gzip で works 805KB / work-texts 393KB /
actors 252KB / staff 155KB / studios 92KB / themes 56KB / series 23KB。

- **新しい生成ファイルに作品を埋め込みたくなったら、まずidで足りないかを疑う**
- **作品詳細ページはあらすじが揃うまで「読み込み中」を出し続ける**こと(`prerender.mjs` が
  「読み込み中」の消滅を待って静的HTMLを書くため、先に描くとあらすじ抜きのHTMLが焼き付く)
- **`useMemo` の依存配列に注意**。エンティティのstateだけを見ていると、後から解決する作品配列で
  再計算されず一覧が空になる

## データ取得パイプライン(TMDb一本柱)

**TMDb API v3(`https://api.themoviedb.org/3`)がAniList(anime-db)の役割を担う。**

- **認証はBearerトークン(API Read Access Token)**。`scripts/.tmdb-token`(**gitignore対象、絶対にコミットしない**)か環境変数`TMDB_TOKEN`から読む。トークンはユーザーのTMDbアカウントで発行済み。APIコールにだけ必要で、**画像CDN(`image.tmdb.org`)へのホットリンクは認証不要**なのでGitHub Actionsビルドにトークンは要らない
- **`scripts/tmdb.py`** … 共有ラッパ。`language=ja-JP`既定(邦題・日本語データ優先、無ければ原語フォールバック)。レート制限は緩い(公式~50req/秒)が既定0.3秒スリープ+429時Retry-After尊重
- **`scripts/suggest_candidates.py`** … discover/movieの人気順で未登録作品をカタログに列挙させる。`--lang ja`で邦画に絞れる。`--min-votes`(既定200)でノイズ除去。出力は`邦題|tmdbId`形式でそのままprobeへ。**日本語ローカライズが無い作品は原題のまま返る**ので目視確認
- **`scripts/probe_tmdb.py`** … 主力裏取りツール。works.jsonとの重複判定(タイトル正規化+tmdbId)を検索前に行いDUPはネットワークアクセスしない。1候補につき監督・脚本・製作会社・キャスト6名・日本公開年月(release_datesのJP劇場公開)・上映時間・ジャンル・ポスターを取得。`regionGuess`(original_language==ja)と`animation`(ジャンルid16)も出す
  - **海外作品の人名はTMDbでも英語表記で返ることがある**(例: Frank Darabont、Chris Buck。有名俳優はカタカナで返ることが多い)。登録は日本で流通しているカタカナ表記に直し、sourceNoteに「TMDb表記: ...」を書き残す
  - **役名(character)は英語で返ることが多い**。登録時に日本語の役名表記へ直す
  - **同名リメイク・続編の誤マッチに注意**(『告白』のような一般名詞タイトルは特に)。OKでもtitleの目視確認を省略しない
- **`scripts/fetch-covers.mjs`** … works.jsonの`tmdbId`をキーに`/movie/{id}`を直接引くため、タイトル検索ベースと違い誤ヒットが構造的に起きない。画像は`image.tmdb.org/t/p/w500{poster_path}`へのホットリンク。検証はcontent-type+実バイト数。`--only`/`--force`(非破壊)/`--retry-misses`
- **`scripts/apply_batch.py`** … キーは`newStaff`/`newStudios`/`newActors`/`newSeries`/`newThemes`/`newAwards`/`works`。**applyは1回だけ**、実行前に既存id衝突件数をレポートで確認する
- **`scripts/find_people.py --names 是枝裕和 東宝 菅田将暉`** … staff/studios/actorsの既存idをJSON全体を読まずに引く。バッチ前に必ず通す
- あらすじは150〜250字で**必ず独自要約**(TMDbのoverviewも転記禁止)。書き出し後に`[Ѐ-ӿ가-힯]`と`[A-Za-z]{4,}`で機械点検する(「原題は The ...。」のような文はoriginalTitleフィールドと重複するのであらすじに書かない — シード時にこの点検で検出して削除した)

## 購入リンク・画像

- 購入リンクは`amazonSearchUrl(title, "Blu-ray")`(`src/ui/common/WorkCover.tsx`)の検索URLのみ。アフィリエイトタグ`izenmi-22`(姉妹サイト共通)。AffiliateNoticeはAmazonのみの表記に変更済み(楽天は本サイトでは不使用)
- **配信リンクも検索URL方式のみ**: `netflixSearchUrl`(netflix.com/search)と`primeVideoSearchUrl`(Amazonの`i=instant-video`検索、アフィリエイトタグ有効)。作品ごとの配信有無・配信先IDはラインアップ変動で誤リンク化するため**意図的にデータ化しない**(TMDbのwatch/providersを使う案は見送り)
- ポスターはTMDbのw500(縦長)で、既存の表紙枠CSSがそのまま合う。**Aboutページに出典と削除対応の記載+TMDb規約必須のクレジット文**(This product uses the TMDB API but is not endorsed or certified by TMDB.)を置いている

## デザイン方針

- **メインアクセントはシネマゴールド(`--color-gold`/`-strong`/`-deep`)**。ranobe-db水色・manga-dbオレンジ・game-dbグリーン・mystery-db藤色・tech-dbティール・anime-db桜ピンクと区別。装飾用パステルの`--color-yellow`とは別変数
- **公開区分バッジ(`.season-badge`、公開年月=gold/邦画=blue/海外=peach/アニメ=purple)**。クラス名はscaffold由来の`season-badge`のまま(汎用ピルバッジとして流用)。ただし**作品カードでは`.season-badge--quiet`を併用して枠線だけのラベルにする**(一覧では作品名とスタッフを先に読ませたいため。塗るのは作品詳細だけ)
- ページ背景は黒一色固定、装飾最小、見出し`M PLUS Rounded 1c`。favicon(`public/favicon.svg`)は黒背景+「映」の1文字ロゴ(`#ffc85c`)。全面塗り(角丸なし)でアルファを残さない
- Google Analytics: **設置済み**。movie-db専用のGA4測定ID `G-6Z3LKHTV0X` を`index.html`の`<head>`に記載(姉妹サイトのIDは流用しない)
- Google Search Console: **sitemap登録済み**(2026-08-11、ユーザーが実施)

## コマンド

```sh
npm install
npm run dev       # http://localhost:5173/movie-db/
npm run build      # 型チェック + データ整合性チェック + ビルド + プリレンダー
npm run preview
npm run fetch-covers
node scripts/generate-ogp.mjs    # 手動実行
node scripts/generate-icons.mjs  # 手動実行
```

`main`へのpushで`.github/workflows/deploy.yml`が自動ビルド・GitHub Pagesデプロイを行う。SEO/SSG(useSeo・prerender.mjs・sitemap生成・SITE_ORIGIN定数の理由)はmystery-dbのCLAUDE.mdの記述がそのまま当てはまる。**プリレンダーのポート4319が他プロジェクトのpreviewに使われていることがある**(`PRERENDER_PORT=4327 npm run build`で回避。2026-08-08に実際に踏んだ)。

## データ規模の推移

25作品(初回シード、2026-08-08) → 1031作品(2026-08-09) → **2086作品**(2026-08-09に候補プールを完全消化+受賞作を追加)。
邦画894(実写)・海外1192、実写1406・アニメ680。年代は2010年代608・2000年代389・2020年代432が中心で、1920〜40年代も12本収録。
シリーズ226・スタッフ2314・制作会社1228・キャスト3071・テーマ70。**ポスターは2086/2086(100%)解決**。
**受賞歴は380作品に558件**(キネマ旬報330・アカデミー賞79・ブルーリボン58・日本アカデミー47・カンヌ44)。

## 大量追加パイプライン(`scripts/bulk.py`。数百件規模の追加はこれを使う)

TMDbが `language=en-US` で人名のラテン表記、`ja-JP` で日本語表記を返し分けることを利用して、
**slug採番・nameKana生成・既存エンティティ照合を全自動化**した。モデルが書くのは
「邦題のかな・あらすじ・日本語の役名・カタカナ社名」だけになる。

```sh
python3 scripts/bulk.py sweep --pages 20 --min-votes 200   # 候補プールを作る(work/candidates.json)
python3 scripts/bulk.py draft --tag bNN --n 40             # 40件裏取りして work/bNN.todo.txt を出す
#   → todo を読んで work/bNN.fill.txt を書く(書式は bulk.py の docstring)
python3 scripts/bulk.py finalize --tag bNN                 # 検証してバッチJSON化(何度でもやり直せる)
python3 scripts/apply_batch.py work/bNN.batch.json         # 反映(applyは成功した1回だけ)
```

- `work/` は**gitignore対象**。`candidates.json`(候補プール)・`used.json`(消費済みtmdbId)・
  `entity-cache.json`(人物のja/en名)・`studio-aliases.json`(社名→studioId)が蓄積され、次のバッチが軽くなる
- **あらすじは5文書く**。4文だと125字前後になり finalize の下限130字に引っかかる。最後の1文を
  「作品の位置づけ・評価・見どころ」にすると150〜250字の基準に自然に収まる
- テーマidは themes.json にあるものだけ(`game`/`science` は無い。ゲーム原作は originalType=game)
- ラテン文字・数字混じりの邦題(PERFECT DAYS/HELLO WORLD/AKIRA/アメスパ2 等)は titleKana が
  自動生成されないので fill で必ず指定する
- 日活ロマンポルノ・ギニーピッグ等のポルノ/ゴア専門作品は `X|<slug>` で落とす方針で運用した
- `kana.py` はローマ字→ひらがな変換。日本人名は en の「名 姓」を反転して生成する(Hiroki Hasegawa
  → はせがわひろき)。**titleKanaは全てひらがな**、**人名・社名のnameKanaはカタカナ**(既存データの慣習)

## 受賞歴パイプライン(`scripts/awards_wiki.py` → `scripts/apply_awards.py`)

Wikipediaの各賞ページから受賞作を機械抽出し、works.json と突合する。**コンテキストには件数しか載らない**のでトークンを消費しない。

```sh
python3 scripts/awards_wiki.py    # 抽出→突合。work/award-hits.json / award-miss.json / award-far.json
python3 scripts/apply_awards.py   # hits を works.json の awardResults に反映(冪等)
```

- 参照ページ: `アカデミー作品賞` / `パルム・ドール` / `日本アカデミー賞` / `ブルーリボン賞_(映画)` / `キネマ旬報`(各年のベスト・テン)。取得結果は `work/wiki-cache/` にキャッシュされる
- **突合は「タイトル正規化 + 公開年の窓(受賞年-3〜+4)」**。同名異作(『西部戦線異状なし』1929/2022、『禁じられた遊び』1953/2023 等)を弾くためで、窓を外れたものは `award-far.json` に保留されて**自動では入らない**。日本公開が大幅に遅れた作品(『風と共に去りぬ』等)は `awards_wiki.py` の `ALLOW` に明示する
- キネマ旬報は日本映画/外国映画のベスト・テン各10位までを `日本映画 第N位` の形で入れる。読者選出と「年代別ベスト・テン」は除外している(後者を含めると年が壊れる)
- **第2段(未登録の受賞作を追加)** は `python3 scripts/bulk.py seed --file work/award-seed.json` でタイトル+年をTMDb検索して候補プールの先頭に差し込み、通常の draft → fill → finalize に流す
- キネマ旬報の未登録分は1500件超あるが大半が戦前〜昭和の小品なので、主要4賞(アカデミー作品賞・パルム・ドール・日本アカデミー最優秀作品賞・ブルーリボン作品賞)を優先して消化した

## 既知の未着手事項

- **キネマ旬報ベスト・テンの未登録作が約1500件**(戦前〜昭和の日本映画が中心)。必要なら `work/award-miss.json` から seed して追加できる
- **作品単位の姉妹サイト相互リンクが未設定**。`relatedAnimeUrl`(君の名は。天気の子などanime-db重複作品)、`relatedNovelUrl`/`relatedComicUrl`(告白・ショーシャンク・SLAM DUNKなど原作もの)を手動設定する。サイト単位のリンク(各サイトのSISTER_SITESカード)は2026-08-09に6サイトすべて設定済み
