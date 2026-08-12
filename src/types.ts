// ---- source data (public/data/source/*.json, hand-authored, committed) ----

export interface ExternalLinks {
  wikipediaUrl?: string;
  officialUrl?: string;
}

export interface AwardResult {
  awardId: string;
  year: number;
  result: string; // free text: "作品賞" / "パルム・ドール" / "第1位" など
}

/** 邦画か海外映画か。合作は主たる製作国で決め、詳細は sourceNote に書く。 */
export type WorkRegion = "japan" | "overseas";

/** 実写かアニメーションか。アニメ映画は anime-db(単独劇場アニメのみ収録)と一部重複するが、
 *  映画DBとしては自然な収録範囲なので含める。重複作品は relatedAnimeUrl で相互リンクする。 */
export type WorkMedium = "liveaction" | "animation";

/** 原作メディアの種別。姉妹サイトへの相互リンクとフィルターの軸。 */
export type OriginalType = "manga" | "lightnovel" | "novel" | "game" | "original" | "other";

export interface CastCredit {
  actorId: string;
  /** 演じた役名。 */
  character: string;
}

export interface WorkSource {
  id: string;
  /** 邦題(日本公開時のタイトル)。 */
  title: string;
  titleKana: string;
  /** 原題。邦題と同じ邦画では省略する。 */
  originalTitle?: string;
  /** 監督(ids into staff.json)。共同監督対応、最低1名必須。 */
  directorIds: string[];
  /** 脚本(ids into staff.json)。監督兼任のみの作品では空でよい。 */
  screenwriterIds: string[];
  /** 制作会社(ids into studios.json)。共同製作対応、最低1社必須。
   *  製作委員会・出資のみの会社は登録しない。 */
  studioIds: string[];
  /** 主要キャスト。裏取りコストを抑えるため最大5名までにとどめる。 */
  cast: CastCredit[];
  themeIds: string[];
  /** 所属シリーズ(id into series.json)。単発作品では省略。 */
  seriesId?: string;
  region: WorkRegion;
  medium: WorkMedium;
  /** 公開時期。海外作品は日本公開年を基本とし、判別が難しいときは本国公開年(sourceNoteに明記)。
   *  month は裏取りできたときだけ入れる。 */
  release: { year: number; month?: number };
  /** 上映時間(分)。 */
  runtime?: number;
  /** 続編・リメイク・シリーズ展開の自由記述。 */
  seriesNote?: string;
  originalType: OriginalType;
  /** 150〜250 chars, written from scratch. */
  synopsis: string;
  awardResults?: AwardResult[];
  /** TMDbの作品ID。fetch-covers.mjs がポスター取得のキーに使う(あいまい検索を避ける)。 */
  tmdbId?: number;
  /** 姉妹サイトの関連作品ページへの相互リンク(当面は手動設定)。 */
  relatedNovelUrl?: string;
  relatedComicUrl?: string;
  relatedMysteryUrl?: string;
  relatedGameUrl?: string;
  relatedAnimeUrl?: string;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

/** 監督・脚本の人物。game-dbのcompanies.jsonと同じ「単一ファイル複数ロール」方式で、
 *  directorIds と screenwriterIds の両方から参照される(兼任が多いため)。 */
export interface StaffSource {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  birthYear?: number;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

export interface StudioSource {
  id: string;
  name: string;
  nameKana: string;
  parentCompany?: string;
  description: string;
  foundedYear?: number;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

export type ActorSource = StaffSource;

/** シリーズ(「ゴジラ」シリーズ等)。1作でも「シリーズものである」ことに意味があるので、
 *  該当作品が1本でもエンティティ化してよい。 */
export interface SeriesSource {
  id: string;
  name: string;
  nameKana: string;
  description?: string;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

export interface ThemeSource {
  id: string;
  name: string;
  description?: string;
  /** そのタグが付いていると知ること自体が展開のネタバレになるもの(どんでん返し等)だけ true。 */
  spoiler?: boolean;
}

export interface AwardSource {
  id: string;
  name: string;
  organizer: string;
  description: string;
  firstYear?: number;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

// ---- generated data (public/data/generated/*.json, built by scripts/generate-manifest.mjs) ----

export interface CastCreditGenerated extends CastCredit {
  actorName: string;
}

/** Denormalized work: source fields plus resolved names for direct rendering. */
/** あらすじ・出典メモ・updatedAt は含まない — 作品詳細ページでしか使わないのに works.json の
 *  大きな割合を占めていたので work-texts.json に分けてある(WorkTexts / getWorkTexts)。 */
export interface WorkGenerated extends Omit<WorkSource, "synopsis" | "sourceNote" | "updatedAt"> {
  directorNames: string[];
  /** Resolved from seriesId at build time; absent for standalone works. */
  seriesName?: string;
  screenwriterNames: string[];
  studioNames: string[];
  castGenerated: CastCreditGenerated[];
  themeNames: string[];
  /** Ids of this work's themes that carry `spoiler: true`, so WorkCard can drop them without
   *  having to fetch themes.json itself. */
  spoilerThemeIds: string[];
  awardSummaries: { awardId: string; awardName: string; year: number; result: string }[];
  /** Resolved at build time from public/data/source/covers-cache.json (see scripts/fetch-covers.mjs).
   *  Absent when no poster could be matched — callers must fall back to the placeholder. */
  coverUrl?: string;
  /** Ids of similar works, best first, computed at build time by generate-manifest.mjs.
   *  Only present in generated/works.json — the copies embedded in the cross-reference lists
   *  omit it to keep those files small. */
  relatedWorkIds?: string[];
}

/** スタッフ詳細ページ用: 監督作品と脚本作品を分けて持つ(game-dbのroles方式)。 */
export interface StaffGenerated {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** 実データは works.json 側。表示側で id から引き直す。 */
  directedWorkIds: string[];
  writtenWorkIds: string[];
}

export interface StudioGenerated {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** 実データは works.json 側。表示側で id から引き直す。 */
  workIds: string[];
}

export interface ActorRole {
  character: string;
  workId: string;
}

export interface ActorGenerated {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** Sorted by release.year ascending — the order the actor's filmography unfolded. */
  roles: ActorRole[];
}

export interface SeriesGenerated {
  id: string;
  name: string;
  nameKana: string;
  description?: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** Sorted by release ascending — シリーズを追う順で固定表示するため。 */
  /** 実データは works.json 側。表示側で id から引き直す。 */
  workIds: string[];
}

export interface ThemeGenerated extends ThemeSource {
  workCount: number;
  /** 実データは works.json 側。表示側で id から引き直す。 */
  workIds: string[];
}

export interface AwardWinner {
  workId: string;
  workTitle: string;
  year: number;
  result: string;
  /** 並べ替え用に result から取り出した順位。順位表記がないものは大賞系=0 / その他=900。 */
  rank: number;
}

export interface AwardGenerated extends AwardSource {
  workCount: number;
  winners: AwardWinner[];
}

/** 作品詳細ページだけが読む長文(generated/work-texts.json)。キーは作品id。 */
export type WorkTexts = Record<string, { synopsis: string; sourceNote: string }>;

export interface Counts {
  works: number;
  series: number;
  staff: number;
  studios: number;
  actors: number;
  themes: number;
  awards: number;
}
