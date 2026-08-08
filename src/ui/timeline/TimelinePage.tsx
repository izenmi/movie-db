import { useMemo } from "react";
import { Link } from "react-router-dom";
import { getWorks } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { colorForYear } from "../common/yearColor";
import { releaseSortKey } from "../common/labels";
import { useSeo } from "../common/useSeo";
import type { WorkGenerated } from "../../types";

interface YearGroup {
  year: number;
  works: WorkGenerated[];
}

/** 公開年表: 年(降順)で全作品をグルーピングした一枚もの。anime-dbの放送クール年表の
 *  映画版で、クールの区切りは持たず年内は公開月順に並べる。
 *  「あの年に何が公開されたか」を辿るページなのでカードではなくコンパクトなリスト表示。 */
export function TimelinePage() {
  const worksState = useAsyncData(getWorks, []);

  const years = useMemo<YearGroup[]>(() => {
    if (worksState.status !== "ready") return [];
    const byYear = new Map<number, WorkGenerated[]>();
    for (const w of worksState.data) {
      if (!byYear.has(w.release.year)) byYear.set(w.release.year, []);
      byYear.get(w.release.year)!.push(w);
    }
    return [...byYear.entries()]
      .sort((a, b) => b[0] - a[0])
      .map(([year, list]) => ({
        year,
        works: [...list].sort(
          (a, b) => releaseSortKey(a) - releaseSortKey(b) || a.titleKana.localeCompare(b.titleKana, "ja"),
        ),
      }));
  }, [worksState]);

  useSeo({
    title: "公開年表",
    description:
      worksState.status === "ready"
        ? `収録映画${worksState.data.length}作品を公開年ごとに並べた年表。各年の公開作品を一望できます。`
        : undefined,
  });

  return (
    <div className="page">
      <h1>公開年表</h1>
      {worksState.status === "loading" && <Loading />}
      {worksState.status === "error" && <ErrorState error={worksState.error} />}
      {worksState.status === "ready" && years.length === 0 && <EmptyState />}
      {worksState.status === "ready" && years.length > 0 && (
        <>
          <p className="page-subtitle">{worksState.data.length}作品</p>
          {years.map((yearGroup) => (
            <div className="home-section" key={yearGroup.year}>
              <h2 className="home-section__heading font-display">
                <span className={`winner-year winner-year--${colorForYear(yearGroup.year)}`}>{yearGroup.year}</span>年
              </h2>
              <ul className="winner-list">
                {yearGroup.works.map((w) => (
                  <li key={w.id}>
                    {w.release.month != null && (
                      <span className="entity-list__count">{w.release.month}月 </span>
                    )}
                    <Link to={`/works/${w.id}`}>{w.title}</Link>
                    <span className="entity-list__count">
                      {" "}
                      {w.studioNames.join("・")}
                      {w.region === "overseas" && " / 海外"}
                      {w.medium === "animation" && " / アニメ"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
