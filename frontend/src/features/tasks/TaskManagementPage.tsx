import { Filter, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Button,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  TaskBulkDeleteResult,
  TaskManagementItem,
  TaskManagementPage as TaskManagementResponse,
} from "../../lib/api/types";
import { formatDate } from "../../lib/format";
import { useSearchParams } from "../../lib/router";
import { useApi } from "../../lib/useApi";
import styles from "./taskManagement.module.css";

const STATUS_OPTIONS = [
  ["planned", "Planifiée"],
  ["active", "En cours"],
  ["awaiting_validation", "À valider"],
  ["completed", "Terminée"],
  ["closed_early", "Clôturée avant achèvement"],
] as const;

export function TaskManagementPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [employee, setEmployee] = useState(params.get("employee_id") ?? "");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [mutationError, setMutationError] = useState("");
  const query = params.toString();
  const { data, error, loading, reload } = useApi<TaskManagementResponse>(
    `/api/v1/task-management/${query ? `?${query}` : ""}`,
  );
  const selectedItems = useMemo(
    () => data?.items.filter((item) => selected.has(item.id)) ?? [],
    [data, selected],
  );

  useEffect(() => setSelected(new Set()), [params]);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (q.trim()) next.set("q", q.trim());
    if (status) next.set("status", status);
    if (employee) next.set("employee_id", employee);
    setParams(next);
  }

  function changePage(page: number) {
    const next = new URLSearchParams(params);
    if (page > 1) next.set("page", String(page));
    else next.delete("page");
    setParams(next);
  }

  async function deleteSelection(event: FormEvent) {
    event.preventDefault();
    setMutationError("");
    try {
      const result = await apiFetch<TaskBulkDeleteResult>(
        "/api/v1/tasks/bulk-delete/",
        {
          method: "POST",
          body: JSON.stringify({
            assignments: selectedItems.map(({ id, revision }) => ({
              id,
              revision,
            })),
            reason,
            confirmation,
          }),
        },
      );
      setMessage(
        `${result.deleted_tasks} tâche(s) supprimée(s). Journal nº ${result.audit_id}.`,
      );
      setConfirming(false);
      setReason("");
      setConfirmation("");
      setSelected(new Set());
      await reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Suppression impossible.",
      );
    }
  }

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Administration IT</p>
          <h1>Gestion des tâches</h1>
          <p>
            Filtrez puis supprimez les tâches avec contrôle de révision et
            audit.
          </p>
        </div>
        <Button
          variant="danger"
          disabled={!selectedItems.length}
          onClick={() => setConfirming(true)}
        >
          <Trash2 size={18} aria-hidden="true" /> Supprimer (
          {selectedItems.length})
        </Button>
      </header>
      {message && (
        <p className="success-banner" role="status">
          {message}
        </p>
      )}
      <form className={styles.filters} onSubmit={applyFilters}>
        <div className="form-field">
          <label htmlFor="task-admin-q">Recherche</label>
          <input
            id="task-admin-q"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
        </div>
        <div className="form-field">
          <label htmlFor="task-admin-status">Statut</label>
          <select
            id="task-admin-status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">Tous</option>
            {STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="task-admin-employee">Collaborateur</label>
          <select
            id="task-admin-employee"
            value={employee}
            onChange={(event) => setEmployee(event.target.value)}
          >
            <option value="">Tous</option>
            {data?.employees.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.filterActions}>
          <Button>
            <Filter size={18} aria-hidden="true" /> Appliquer
          </Button>
          <Button
            type="button"
            variant="quiet"
            onClick={() => {
              setQ("");
              setStatus("");
              setEmployee("");
              setParams(new URLSearchParams());
            }}
          >
            <RotateCcw size={18} aria-hidden="true" /> Réinitialiser
          </Button>
        </div>
      </form>
      {loading && <Skeleton label="Chargement des tâches" />}
      {error && <ErrorState error={error} retry={() => void reload()} />}
      {data && !data.items.length && (
        <EmptyState title="Aucune tâche">
          Aucune tâche ne correspond aux filtres.
        </EmptyState>
      )}
      {data && data.items.length > 0 && (
        <>
          <p className={styles.resultCount}>{data.total} tâche(s)</p>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Sélection</th>
                  <th>Tâche</th>
                  <th>Collaborateur</th>
                  <th>Responsable</th>
                  <th>Statut</th>
                  <th>Progression</th>
                  <th>Période</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item: TaskManagementItem) => (
                  <tr
                    key={item.id}
                    className={selected.has(item.id) ? styles.selectedRow : ""}
                  >
                    <td data-label="Sélection">
                      <input
                        type="checkbox"
                        aria-label={`Sélectionner ${item.code}`}
                        checked={selected.has(item.id)}
                        onChange={() =>
                          setSelected((current) => {
                            const next = new Set(current);
                            if (next.has(item.id)) next.delete(item.id);
                            else next.add(item.id);
                            return next;
                          })
                        }
                      />
                    </td>
                    <td data-label="Tâche">
                      <strong>{item.code}</strong>
                      <span>{item.title}</span>
                    </td>
                    <td data-label="Collaborateur">{item.employee.name}</td>
                    <td data-label="Responsable">{item.manager.name}</td>
                    <td data-label="Statut">
                      <StatusBadge status={item.status}>
                        {item.status_label}
                      </StatusBadge>
                    </td>
                    <td data-label="Progression">{item.percentage} %</td>
                    <td data-label="Période">
                      {formatDate(item.start_date)} –{" "}
                      {formatDate(item.due_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.pages > 1 && (
            <nav className={styles.pagination} aria-label="Pagination">
              <Button
                variant="quiet"
                disabled={data.page <= 1}
                onClick={() => changePage(data.page - 1)}
              >
                Précédent
              </Button>
              <span>
                Page {data.page} sur {data.pages}
              </span>
              <Button
                variant="quiet"
                disabled={data.page >= data.pages}
                onClick={() => changePage(data.page + 1)}
              >
                Suivant
              </Button>
            </nav>
          )}
        </>
      )}
      {confirming && (
        <div className={styles.modalBackdrop}>
          <section
            className={styles.modal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <h2 id="delete-title">
              Supprimer {selectedItems.length} tâche(s) ?
            </h2>
            <p>Cette opération est définitive et conserve un témoin d’audit.</p>
            <form
              className="stack"
              onSubmit={(event) => void deleteSelection(event)}
            >
              <div className="form-field">
                <label htmlFor="delete-reason">Motif</label>
                <textarea
                  id="delete-reason"
                  required
                  minLength={3}
                  maxLength={500}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="delete-confirmation">Saisir SUPPRIMER</label>
                <input
                  id="delete-confirmation"
                  required
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                />
              </div>
              {mutationError && (
                <p className="error-banner" role="alert">
                  {mutationError}
                </p>
              )}
              <div className="cluster">
                <Button
                  variant="danger"
                  disabled={confirmation !== "SUPPRIMER"}
                >
                  Supprimer définitivement
                </Button>
                <Button
                  type="button"
                  variant="quiet"
                  onClick={() => setConfirming(false)}
                >
                  Annuler
                </Button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
