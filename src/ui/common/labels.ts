import type { OriginalType, WorkGenerated, WorkMedium, WorkRegion } from "../../types";

/** 「2016年8月」のような公開時期の表示文字列。月が未裏取りの作品は年だけ。 */
export function releaseLabel(release: { year: number; month?: number }): string {
  return release.month != null ? `${release.year}年${release.month}月` : `${release.year}年`;
}

/** 年内の公開月まで含めた並べ替えキー(昇順)。月が無い作品は年初扱い。 */
export function releaseSortKey(w: WorkGenerated): number {
  return w.release.year * 100 + (w.release.month ?? 0);
}

export const REGION_LABEL: Record<WorkRegion, string> = {
  japan: "邦画",
  overseas: "海外映画",
};

export const MEDIUM_LABEL: Record<WorkMedium, string> = {
  liveaction: "実写",
  animation: "アニメ",
};

export const ORIGINAL_TYPE_LABEL: Record<OriginalType, string> = {
  manga: "漫画原作",
  lightnovel: "ライトノベル原作",
  novel: "小説原作",
  game: "ゲーム原作",
  original: "オリジナル",
  other: "その他原作",
};
