import { useState } from "react";
import { getSeries, getWorks } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { useSeo } from "../common/useSeo";
import { SeriesCard } from "./SeriesCard";

/** 収録作品数の多い順。1作しかないシリーズもページ自体は存在するが、一覧の既定表示からは畳んでおく。
 *  続編がまだ登録されていないだけのものが大半で、そのまま並べると一覧が薄まるため。 */
export function SeriesListPage() {
  const state = useAsyncData(getSeries, []);
  // カードのポスター・監督・テーマは works.json 側にある(SeriesGenerated は workIds のみ)。
  const worksState = useAsyncData(getWorks, []);
  const worksById = new Map(
    (worksState.status === "ready" ? worksState.data : []).map((w) => [w.id, w]),
  );
  const worksOf = (ids: string[]) =>
    ids.map((id) => worksById.get(id)).filter((w) => w !== undefined);
  const [showSingles, setShowSingles] = useState(false);
  const [q, setQ] = useState("");

  useSeo({
    title: "シリーズ一覧",
    description:
      state.status === "ready"
        ? `映画シリーズ${state.data.length}件の一覧。収録作品数の多い順。シリーズごとに作品を新しい順で辿れます。`
        : undefined,
  });

  const all = state.status === "ready" ? state.data : [];
  const keyword = q.trim().toLowerCase();
  const matched = keyword
    ? all.filter((s) => s.name.toLowerCase().includes(keyword) || s.nameKana.includes(keyword))
    : all;
  const multi = matched.filter((s) => s.workCount > 1);
  const singles = matched.filter((s) => s.workCount <= 1);

  return (
    <div className="page">
      <h1>シリーズ一覧</h1>
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        <>
          <p className="page-subtitle">
            {multi.length}シリーズ（2作以上）
            {singles.length > 0 && ` / 1作のみ ${singles.length}件`}
          </p>
          <div className="filter-row">
            <input
              type="search"
              value={q}
              placeholder="シリーズ名で絞り込み"
              aria-label="シリーズ名で絞り込み"
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          {multi.length === 0 && singles.length === 0 && <EmptyState />}
          <div className="series-grid">
            {multi.map((s) => (
              <SeriesCard series={s} works={worksOf(s.workIds)} key={s.id} />
            ))}
          </div>
          {singles.length > 0 && (
            <>
              <button
                type="button"
                className="filter-clear-btn"
                aria-expanded={showSingles}
                onClick={() => setShowSingles((v) => !v)}
              >
                {showSingles ? "1作のみのシリーズを隠す" : `1作のみのシリーズも表示（${singles.length}件）`}
              </button>
              {showSingles && (
                <div className="series-grid">
                  {singles.map((s) => (
                    <SeriesCard series={s} works={worksOf(s.workIds)} key={s.id} />
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
