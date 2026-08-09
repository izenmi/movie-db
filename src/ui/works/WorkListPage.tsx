import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { getSeries, getStudios, getThemes, getWorks } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { useSeo } from "../common/useSeo";
import { MEDIUM_LABEL, ORIGINAL_TYPE_LABEL, REGION_LABEL, releaseSortKey } from "../common/labels";
import { WorkGrid } from "../common/WorkGrid";
import { useCoverView } from "../common/useCoverView";

const ORIGINAL_TYPE_OPTIONS = (Object.entries(ORIGINAL_TYPE_LABEL) as [string, string][]).map(
  ([value, label]) => ({ value, label }),
);

const REGION_OPTIONS = (Object.entries(REGION_LABEL) as [string, string][]).map(([value, label]) => ({
  value,
  label,
}));

const MEDIUM_OPTIONS = (Object.entries(MEDIUM_LABEL) as [string, string][]).map(([value, label]) => ({
  value,
  label,
}));

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "year-desc", label: "公開が新しい順" },
  { value: "year-asc", label: "公開が古い順" },
  { value: "kana", label: "五十音順" },
];

const PAGE_SIZE = 50;

/** Numbered page list with "…" collapsing for large totals, e.g. [1,2,3,"…",710].
 *  Always keeps a 3-page window around the current page plus the first/last page pinned;
 *  collapses to a plain 1..totalPages list when everything already fits without gaps. */
function getPageNumbers(page: number, totalPages: number): (number | "ellipsis")[] {
  const windowSize = 3;
  if (totalPages <= windowSize + 2) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  let start: number;
  if (page <= windowSize) {
    start = 1;
  } else if (page > totalPages - windowSize) {
    start = totalPages - windowSize + 1;
  } else {
    start = page - 1;
  }
  const end = start + windowSize - 1;

  const items: (number | "ellipsis")[] = [];
  if (start > 1) {
    items.push(1);
    if (start > 2) items.push("ellipsis");
  }
  for (let n = start; n <= end; n++) items.push(n);
  if (end < totalPages) {
    if (end < totalPages - 1) items.push("ellipsis");
    items.push(totalPages);
  }
  return items;
}

function Pager({ page, totalPages, onGoToPage }: { page: number; totalPages: number; onGoToPage: (page: number) => void }) {
  return (
    <div className="pager">
      <button type="button" className="pager__prev" disabled={page <= 1} onClick={() => onGoToPage(page - 1)}>
        ← 前へ
      </button>
      <ol className="pager__pages">
        {getPageNumbers(page, totalPages).map((item, i) =>
          item === "ellipsis" ? (
            <li className="pager__ellipsis" key={`ellipsis-${i}`} aria-hidden="true">
              …
            </li>
          ) : (
            <li key={item}>
              <button
                type="button"
                className={item === page ? "pager__page pager__page--active" : "pager__page"}
                aria-current={item === page ? "page" : undefined}
                onClick={() => onGoToPage(item)}
              >
                {item}
              </button>
            </li>
          ),
        )}
      </ol>
      <button type="button" className="pager__next" disabled={page >= totalPages} onClick={() => onGoToPage(page + 1)}>
        次へ →
      </button>
    </div>
  );
}

export function WorkListPage() {
  const [params, setParams] = useSearchParams();
  const { coverView, toggle } = useCoverView();
  const q = params.get("q") ?? "";
  const themeId = params.get("theme") ?? "";
  const studioId = params.get("studio") ?? "";
  const seriesId = params.get("series") ?? "";
  const originalType = params.get("originalType") ?? "";
  const region = params.get("region") ?? "";
  const medium = params.get("medium") ?? "";
  const decade = params.get("decade") ?? "";
  const award = params.get("award") ?? "";
  const sort = params.get("sort") ?? "year-desc";
  const pageParam = Math.max(1, parseInt(params.get("page") ?? "1", 10) || 1);

  const worksState = useAsyncData(getWorks, []);
  const themesState = useAsyncData(getThemes, []);
  const studiosState = useAsyncData(getStudios, []);
  const seriesState = useAsyncData(getSeries, []);

  useSeo({
    title: "作品一覧",
    description:
      worksState.status === "ready"
        ? `邦画・洋画・アニメ映画${worksState.data.length}作品を公開年・テーマ・制作会社・原作種別などから検索・絞り込みできます。`
        : undefined,
  });

  // 選択肢は収録作品が実在する年代だけを出す(空の選択肢を並べない)。
  const decadeOptions = useMemo(() => {
    if (worksState.status !== "ready") return [];
    const decades = [...new Set(worksState.data.map((w) => Math.floor(w.release.year / 10) * 10))];
    return decades.sort((a, b) => b - a).map((d) => ({ value: String(d), label: `${d}年代` }));
  }, [worksState]);

  const filtered = useMemo(() => {
    if (worksState.status !== "ready") return [];
    const keyword = q.trim().toLowerCase();
    return worksState.data.filter((w) => {
      if (keyword) {
        const haystack = `${w.title}${w.titleKana}${w.directorNames.join("")}${w.studioNames.join("")}${w.castGenerated
          .map((c) => c.actorName)
          .join("")}`.toLowerCase();
        if (!haystack.includes(keyword)) return false;
      }
      if (themeId && !w.themeIds.includes(themeId)) return false;
      if (studioId && !w.studioIds.includes(studioId)) return false;
      if (seriesId && w.seriesId !== seriesId) return false;
      if (originalType && w.originalType !== originalType) return false;
      if (region && w.region !== region) return false;
      if (medium && w.medium !== medium) return false;
      if (decade && Math.floor(w.release.year / 10) * 10 !== Number(decade)) return false;
      if (award === "yes" && w.awardSummaries.length === 0) return false;
      return true;
    });
  }, [worksState, q, themeId, studioId, seriesId, originalType, region, medium, decade, award]);

  const sorted = useMemo(() => {
    if (sort === "year-asc") return [...filtered].sort((a, b) => releaseSortKey(a) - releaseSortKey(b));
    if (sort === "year-desc") return [...filtered].sort((a, b) => releaseSortKey(b) - releaseSortKey(a));
    if (sort === "kana") return [...filtered].sort((a, b) => a.titleKana.localeCompare(b.titleKana, "ja"));
    return filtered;
  }, [filtered, sort]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const page = Math.min(pageParam, totalPages);
  const pageItems = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setParams(next, { replace: true });
  }

  function goToPage(nextPage: number) {
    const next = new URLSearchParams(params);
    if (nextPage <= 1) next.delete("page");
    else next.set("page", String(nextPage));
    setParams(next, { replace: true });
    window.scrollTo(0, 0);
  }

  function clearFilters() {
    const next = new URLSearchParams(params);
    for (const key of ["q", "theme", "studio", "series", "originalType", "region", "medium", "decade", "award", "page"]) {
      next.delete(key);
    }
    setParams(next, { replace: true });
  }

  const hasActiveFilters = Boolean(q || themeId || studioId || seriesId || originalType || region || medium || decade || award);

  return (
    <div className="page">
      <h1>作品一覧</h1>
      <input
        className="search-box"
        type="search"
        placeholder="作品名・監督・制作会社・キャストで検索"
        value={q}
        onChange={(e) => updateParam("q", e.target.value)}
      />
      <div className="filter-row">
        {themesState.status === "ready" && (
          <select value={themeId} onChange={(e) => updateParam("theme", e.target.value)}>
            <option value="">テーマで絞り込み</option>
            {themesState.data.map((t) => (
              <option value={t.id} key={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        )}
        {studiosState.status === "ready" && (
          <select value={studioId} onChange={(e) => updateParam("studio", e.target.value)}>
            <option value="">制作会社で絞り込み</option>
            {studiosState.data.map((s) => (
              <option value={s.id} key={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        )}
        {seriesState.status === "ready" && seriesState.data.length > 0 && (
          <select value={seriesId} onChange={(e) => updateParam("series", e.target.value)}>
            <option value="">シリーズで絞り込み</option>
            {seriesState.data.map((x) => (
              <option value={x.id} key={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        )}
        <select value={originalType} onChange={(e) => updateParam("originalType", e.target.value)}>
          <option value="">原作種別で絞り込み</option>
          {ORIGINAL_TYPE_OPTIONS.map((o) => (
            <option value={o.value} key={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select value={region} onChange={(e) => updateParam("region", e.target.value)}>
          <option value="">邦画/海外で絞り込み</option>
          {REGION_OPTIONS.map((o) => (
            <option value={o.value} key={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select value={medium} onChange={(e) => updateParam("medium", e.target.value)}>
          <option value="">実写/アニメで絞り込み</option>
          {MEDIUM_OPTIONS.map((o) => (
            <option value={o.value} key={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {decadeOptions.length > 0 && (
          <select value={decade} onChange={(e) => updateParam("decade", e.target.value)}>
            <option value="">年代で絞り込み</option>
            {decadeOptions.map((o) => (
              <option value={o.value} key={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
        <select value={award} onChange={(e) => updateParam("award", e.target.value)}>
          <option value="">受賞歴で絞り込み</option>
          <option value="yes">受賞歴あり</option>
        </select>
        <select
          value={sort}
          onChange={(e) => updateParam("sort", e.target.value === "year-desc" ? "" : e.target.value)}
        >
          {SORT_OPTIONS.map((o) => (
            <option value={o.value} key={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {hasActiveFilters && (
          <button type="button" className="filter-clear-btn" onClick={clearFilters}>
            フィルターをクリア
          </button>
        )}
        {toggle}
      </div>

      {worksState.status === "loading" && <Loading />}
      {worksState.status === "error" && <ErrorState error={worksState.error} />}
      {worksState.status === "ready" && (
        <>
          <p className="page-subtitle">
            {hasActiveFilters ? `${filtered.length}件 / 全${worksState.data.length}件` : `${filtered.length}件`}
            {totalPages > 1 && `(${page} / ${totalPages}ページ)`}
          </p>
          {filtered.length === 0 && <EmptyState />}
          {totalPages > 1 && <Pager page={page} totalPages={totalPages} onGoToPage={goToPage} />}
          <WorkGrid works={pageItems} coverView={coverView} />
          {totalPages > 1 && <Pager page={page} totalPages={totalPages} onGoToPage={goToPage} />}
        </>
      )}
    </div>
  );
}
