import { useLocation, useSearchParams } from "../../lib/router";
import type { Dashboard } from "../../lib/api/types";
import { useApi } from "../../lib/useApi";
import {
  ButtonLink,
  EmptyState,
  ErrorState,
  Skeleton,
} from "../../components/ui";
import { PeriodNavigation } from "./PeriodNavigation";
import { TaskCard } from "./TaskCard";

export function DashboardPage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskView =
    searchParams.get("task_view") === "archives" ? "archives" : "active";
  const { data, error, loading, reload } = useApi<Dashboard>(
    `/api/v1/dashboard/${location.search}`,
  );
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Tableau de bord personnel</p>
          <h1>Mes tâches</h1>
          <p>
            Une vue claire des engagements, de leur progression réelle et de la
            charge restante.
          </p>
        </div>
        <ButtonLink to="/propositions/nouvelle" variant="secondary">
          Proposer une tâche
        </ButtonLink>
      </header>
      {loading && (
        <div className="grid" aria-label="Chargement des tâches">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      )}
      {error && <ErrorState error={error} retry={reload} />}
      {data && (
        <>
          <div className="cluster" role="group" aria-label="Vue des tâches">
            <button
              type="button"
              aria-pressed={taskView === "active"}
              onClick={() => {
                const next = new URLSearchParams(searchParams);
                next.delete("task_view");
                setSearchParams(next);
              }}
            >
              Tâches actives
            </button>
            <button
              type="button"
              aria-pressed={taskView === "archives"}
              onClick={() => {
                const next = new URLSearchParams(searchParams);
                next.set("task_view", "archives");
                setSearchParams(next);
              }}
            >
              Archives
            </button>
          </div>
          <PeriodNavigation
            period={data.period}
            preserveParams={["task_view"]}
          />
          {data.tasks.length ? (
            <div className="grid">
              {data.tasks.map((task) => (
                <TaskCard key={task.id} task={task} />
              ))}
            </div>
          ) : (
            <EmptyState
              title={
                taskView === "archives"
                  ? "Aucune tâche archivée sur cette période"
                  : "Aucune tâche sur cette période"
              }
              action={
                <ButtonLink to="/propositions/nouvelle">
                  Proposer une tâche
                </ButtonLink>
              }
            >
              Vous pouvez changer de période ou proposer un nouvel engagement.
            </EmptyState>
          )}
        </>
      )}
    </>
  );
}
