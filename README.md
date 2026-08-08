# 映画DB

邦画・洋画・アニメ映画を制作会社・監督・脚本・キャスト・公開年・受賞歴・テーマから検索できるファンデータベースです。姉妹サイト [らのべDB](https://izenmi.github.io/ranobe-db/) の映画版として作成しました。邦画/海外・実写/アニメの2軸で絞り込め、公開年の年表で辿れるのが特徴です。

https://izenmi.github.io/movie-db/

## データについて

`public/data/source/*.json` が一次データです。TMDB・Wikipedia日本語版などの公開情報を参考に、あらすじ等は独自の文章で要約して作成しています。ポスター画像は [TMDB](https://www.themoviedb.org/) の画像を参照して表示しており、権利は各作品の権利者に帰属します。本サイトはTMDB APIを利用していますが、TMDBによる承認・認証を受けたものではありません。データの誤りや画像の掲載に問題がある場合はIssueでお知らせください。

`public/data/generated/*.json` はビルド時に `scripts/generate-manifest.mjs` が `source/*.json` から自動生成する非正規化データです(`.gitignore`対象、手で編集しないでください)。

## 開発

```sh
npm install
npm run dev       # http://localhost:5173/movie-db/
npm run build      # 型チェック + データ整合性チェック + ビルド + プリレンダー
npm run preview
npm run fetch-covers
```

`npm run dev` / `npm run build` の前に `scripts/generate-manifest.mjs` が自動実行され、`source/*.json` 内のid参照(スタッフ・スタジオ・声優・テーマ・アワード)に誤りがあるとビルドが失敗します。

## デプロイ

`main` ブランチへのpushで GitHub Actions (`.github/workflows/deploy.yml`) が自動的にビルドしてGitHub Pagesへ公開します。リポジトリ名を変更する場合は `vite.config.ts` の `base` も合わせて変更してください。
