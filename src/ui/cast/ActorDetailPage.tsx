import { useParams } from "react-router-dom";
import { getActor } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { WorkCard, WorkCoverCard } from "../common/WorkCard";
import { useCoverView } from "../common/useCoverView";
import { BASE_PATH, SITE_NAME, breadcrumbJsonLd, useSeo } from "../common/useSeo";

/** 出演作品を公開順(古い順)固定で表示する。各作品の上に演じた役名を添える。
 *  mystery-dbの探偵ページ(発表順固定)と同じ思想で、ソート切替は置かない。 */
export function ActorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const state = useAsyncData(() => getActor(id!), [id]);
  const actor = state.status === "ready" ? state.data : undefined;
  const { coverView, gridClassName, toggle } = useCoverView();

  useSeo({
    title: actor?.name,
    description: actor
      ? `「${actor.name}」の出演映画${actor.workCount}作品を公開順に紹介。${actor.description}`.slice(0, 160)
      : undefined,
    jsonLd: actor
      ? [
          {
            "@context": "https://schema.org",
            "@type": "Person",
            name: actor.name,
            ...(actor.description && { description: actor.description }),
            ...(actor.externalLinks.wikipediaUrl && { sameAs: [actor.externalLinks.wikipediaUrl] }),
          },
          breadcrumbJsonLd([
            { name: SITE_NAME, path: BASE_PATH },
            { name: "キャスト一覧", path: `${BASE_PATH}cast` },
            { name: actor.name, path: `${BASE_PATH}cast/${id}` },
          ]),
        ]
      : undefined,
  });

  return (
    <div className="page">
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && !state.data && <EmptyState text="見つかりませんでした。" />}
      {state.status === "ready" && state.data && (
        <>
          <h1>{state.data.name}</h1>
          <p className="page-subtitle">{state.data.workCount}作品(主要キャストのみ)</p>
          {state.data.description && <p>{state.data.description}</p>}
          {state.data.externalLinks.wikipediaUrl && (
            <p>
              <a href={state.data.externalLinks.wikipediaUrl} target="_blank" rel="noreferrer">
                Wikipediaで見る
              </a>
            </p>
          )}
          <h2 className="home-section__heading font-display">出演作品</h2>
          {state.data.roles.length === 0 && <EmptyState text="出演作品が登録されていません。" />}
          <div className="filter-row">{toggle}</div>
          <div className={gridClassName}>
            {state.data.roles.map((role) => (
              <div key={`${role.work.id}-${role.character}`}>
                <p className="cast-role-label">{role.character} 役</p>
                {coverView ? <WorkCoverCard work={role.work} /> : <WorkCard work={role.work} />}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
