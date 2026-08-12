import { Link } from "react-router-dom";
import type { SeriesGenerated, WorkGenerated } from "../../types";
import { WorkCover } from "../common/WorkCover";

const COVER_COUNT = 4;
const THEME_COUNT = 4;
const DIRECTOR_COUNT = 2;

/** シリーズ一覧のカード。名前と件数だけの行だと、そのシリーズが何の映画なのか一覧から分からない。
 *  作品一覧のカードと同じ密度になるよう、ポスター・公開年の範囲・監督・テーマまで出す。
 *
 *  表示する値はすべて渡された作品から導出していて、シリーズ側に持たせた項目はない。
 *  作品を足せばポスターも年も自動で更新される。 */
export function SeriesCard({ series, works }: { series: SeriesGenerated; works: WorkGenerated[] }) {
  // series.json の works は新しい順(generate-manifest.mjs)。ポスターは第1作から並べたいので
  // ここで公開順に取り直し、年の範囲もその両端から出す。
  const byYear = [...works].sort((a, b) => a.release.year - b.release.year);
  const from = byYear[0]?.release.year;
  const to = byYear[byYear.length - 1]?.release.year;

  // 監督も公開順(第1作の監督が先頭に来るようにする)
  const directors = [...new Set(byYear.flatMap((w) => w.directorNames))];
  // ネタバレテーマは WorkCard と同じ理由で伏せる(一覧を眺めるだけで割れてしまうため)
  const themeCounts = new Map<string, { name: string; n: number }>();
  for (const w of works) {
    const hidden = new Set(w.spoilerThemeIds);
    w.themeIds.forEach((id, i) => {
      if (hidden.has(id)) return;
      const e = themeCounts.get(id) ?? { name: w.themeNames[i] ?? id, n: 0 };
      e.n += 1;
      themeCounts.set(id, e);
    });
  }
  const themes = [...themeCounts.entries()]
    .sort((a, b) => b[1].n - a[1].n || a[1].name.localeCompare(b[1].name, "ja"))
    .slice(0, THEME_COUNT);

  return (
    <div className="series-card">
      <Link to={`/series/${series.id}`} className="work-card__cover-link" aria-label={series.name} />
      <div className="series-card__covers">
        {byYear.slice(0, COVER_COUNT).map((w) => (
          <WorkCover title={w.title} coverUrl={w.coverUrl} size="sm" key={w.id} />
        ))}
      </div>
      <div className="series-card__content">
        <div className="series-card__title">
          {series.name}
          <span className="entity-list__count">{series.workCount}作</span>
        </div>
        {from != null && (
          <div className="work-card__meta">
            <span className="season-badge season-badge--quiet season-badge--year">
              {from === to ? `${from}年` : `${from}年〜${to}年`}
            </span>{" "}
            監督: {directors.slice(0, DIRECTOR_COUNT).join("・")}
            {directors.length > DIRECTOR_COUNT && ` ほか${directors.length - DIRECTOR_COUNT}名`}
          </div>
        )}
        {themes.length > 0 && (
          <div className="chip-row">
            {themes.map(([id, t]) => (
              <Link className="chip" to={`/themes/${id}`} key={id}>
                {t.name}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
