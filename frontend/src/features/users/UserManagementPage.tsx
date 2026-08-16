import {
  Filter,
  PowerOff,
  RotateCcw,
  Trash2,
  UserRoundPlus,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Button,
  ButtonLink,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  ManagedUserSummary,
  UserBulkActionResult,
  UserManagementOptions,
  UserManagementPage as UserPage,
} from "../../lib/api/types";
import { Link, useSearchParams } from "../../lib/router";
import { useApi } from "../../lib/useApi";
import styles from "./users.module.css";

export function UserManagementPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [state, setState] = useState(params.get("state") ?? "");
  const [unit, setUnit] = useState(params.get("unit_id") ?? "");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [action, setAction] = useState<"deactivate" | "delete" | null>(null);
  const [reason, setReason] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [mutationError, setMutationError] = useState("");
  const lastSelected = useRef<number | null>(null);
  const options = useApi<UserManagementOptions>("/api/v1/users/options/");
  const query = params.toString();
  const users = useApi<UserPage>(`/api/v1/users/${query ? `?${query}` : ""}`);
  const selectedItems = useMemo(
    () => users.data?.items.filter((item) => selected.has(item.id)) ?? [],
    [selected, users.data],
  );
  useEffect(() => setSelected(new Set()), [params]);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (q.trim()) next.set("q", q.trim());
    if (state) next.set("state", state);
    if (unit) next.set("unit_id", unit);
    setParams(next);
  }

  function selectable(item: ManagedUserSummary) {
    return item.batch_capabilities.deactivate || item.batch_capabilities.delete;
  }

  function toggleSelection(
    item: ManagedUserSummary,
    checked: boolean,
    extendRange: boolean,
  ) {
    const items = users.data?.items ?? [];
    const previousId = lastSelected.current;
    const currentIndex = items.findIndex(
      (candidate) => candidate.id === item.id,
    );
    setSelected((current) => {
      const next = new Set(current);
      const previousIndex = items.findIndex(
        (candidate) => candidate.id === previousId,
      );
      const candidates =
        extendRange && previousIndex >= 0
          ? items.slice(
              Math.min(previousIndex, currentIndex),
              Math.max(previousIndex, currentIndex) + 1,
            )
          : [item];
      for (const candidate of candidates) {
        if (!selectable(candidate)) continue;
        if (checked) next.add(candidate.id);
        else next.delete(candidate.id);
      }
      return next;
    });
    lastSelected.current = item.id;
  }

  async function applyAction(event: FormEvent) {
    event.preventDefault();
    if (!action) return;
    setMutationError("");
    try {
      const result = await apiFetch<UserBulkActionResult>(
        "/api/v1/users/bulk-action/",
        {
          method: "POST",
          body: JSON.stringify({
            action,
            users: selectedItems.map(({ id, state_token }) => ({
              id,
              state_token,
            })),
            reason,
            confirmation,
          }),
        },
      );
      setMessage(
        `${result.affected} compte(s) ${action === "delete" ? "supprimé(s)" : "désactivé(s)"}.`,
      );
      setSelected(new Set());
      setAction(null);
      setReason("");
      setConfirmation("");
      if (action === "deactivate") {
        const next = new URLSearchParams(params);
        next.set("state", "inactive");
        next.delete("page");
        setState("inactive");
        setParams(next);
      } else {
        await users.reload();
      }
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Action impossible.",
      );
    }
  }

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Administration IT</p>
          <h1>Utilisateurs</h1>
          <p>
            Gérez les comptes et leur rattachement Odoo sans effacer
            l’historique.
          </p>
        </div>
        <ButtonLink to="/administration/utilisateurs/nouveau">
          <UserRoundPlus size={18} aria-hidden="true" /> Ajouter
        </ButtonLink>
      </header>
      {message && (
        <p className="success-banner" role="status">
          {message}
        </p>
      )}
      <form className={styles.filters} onSubmit={applyFilters}>
        <div className="form-field">
          <label htmlFor="user-q">Recherche</label>
          <input
            id="user-q"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
        </div>
        <div className="form-field">
          <label htmlFor="user-state">État</label>
          <select
            id="user-state"
            value={state}
            onChange={(event) => setState(event.target.value)}
          >
            <option value="">Tous</option>
            <option value="active">Actifs</option>
            <option value="inactive">Inactifs</option>
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="user-unit">Unité</label>
          <select
            id="user-unit"
            value={unit}
            onChange={(event) => setUnit(event.target.value)}
          >
            <option value="">Toutes</option>
            {options.data?.units.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} — {item.short_name}
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
              setState("");
              setUnit("");
              setParams(new URLSearchParams());
            }}
          >
            <RotateCcw size={18} aria-hidden="true" /> Réinitialiser
          </Button>
        </div>
      </form>
      {(users.loading || options.loading) && (
        <Skeleton label="Chargement des utilisateurs" />
      )}
      {(users.error || options.error) && (
        <ErrorState
          error={
            users.error ?? options.error ?? new Error("Liste indisponible")
          }
          retry={() => {
            void users.reload();
            void options.reload();
          }}
        />
      )}
      {users.data && !users.data.items.length && (
        <EmptyState title="Aucun utilisateur">
          Aucun compte ne correspond aux filtres.
        </EmptyState>
      )}
      {users.data && users.data.items.length > 0 && (
        <>
          <div className={styles.batchToolbar}>
            <p className={styles.resultCount}>
              {users.data.total} compte(s) · {selectedItems.length}{" "}
              sélectionné(s)
            </p>
            <div className={styles.batchActions}>
              <Button
                variant="quiet"
                disabled={
                  !selectedItems.length ||
                  !selectedItems.every(
                    (item) => item.batch_capabilities.deactivate,
                  )
                }
                onClick={() => setAction("deactivate")}
              >
                <PowerOff size={18} aria-hidden="true" /> Désactiver
              </Button>
              <Button
                variant="danger"
                disabled={
                  !selectedItems.length ||
                  !selectedItems.every((item) => item.batch_capabilities.delete)
                }
                onClick={() => setAction("delete")}
              >
                <Trash2 size={18} aria-hidden="true" /> Supprimer
              </Button>
            </div>
          </div>
          <p className={styles.selectionHint}>
            Utilisez la case d’en-tête pour toute la page ou Maj clic pour une
            plage.
          </p>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="Tout sélectionner"
                      disabled={!users.data.items.some(selectable)}
                      checked={
                        users.data.items.some(selectable) &&
                        users.data.items
                          .filter(selectable)
                          .every((item) => selected.has(item.id))
                      }
                      onChange={(event) => {
                        const checked = event.currentTarget.checked;
                        setSelected((current) => {
                          const next = new Set(current);
                          for (const item of users.data!.items.filter(
                            selectable,
                          )) {
                            if (checked) next.add(item.id);
                            else next.delete(item.id);
                          }
                          return next;
                        });
                        lastSelected.current = null;
                      }}
                    />
                    <span className={styles.visuallyHidden}>Sélection</span>
                  </th>
                  <th>Personne</th>
                  <th>Identifiant</th>
                  <th>Fonction</th>
                  <th>Unité principale</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((item) => (
                  <tr
                    key={item.id}
                    className={selected.has(item.id) ? styles.selectedRow : ""}
                  >
                    <td data-label="Sélection">
                      <input
                        type="checkbox"
                        disabled={!selectable(item)}
                        checked={selected.has(item.id)}
                        readOnly
                        aria-label={`Sélectionner ${item.name}`}
                        onClick={(event) => {
                          toggleSelection(
                            item,
                            !selected.has(item.id),
                            event.shiftKey,
                          );
                        }}
                      />
                    </td>
                    <td data-label="Personne">
                      <Link to={`/administration/utilisateurs/${item.id}`}>
                        <strong>{item.name}</strong>
                      </Link>
                      <span>{item.email}</span>
                    </td>
                    <td data-label="Identifiant">{item.login_alias ?? "—"}</td>
                    <td data-label="Fonction">{item.position || "—"}</td>
                    <td data-label="Unité">
                      {item.primary_unit?.short_name ?? "—"}
                    </td>
                    <td data-label="État">
                      <StatusBadge
                        status={item.is_active ? "completed" : "rejected"}
                      >
                        {item.is_active ? "Actif" : "Inactif"}
                      </StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {users.data.pages > 1 && (
            <nav className={styles.pagination}>
              <Button
                variant="quiet"
                disabled={users.data.page <= 1}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("page", String(users.data!.page - 1));
                  setParams(next);
                }}
              >
                Précédent
              </Button>
              <span>
                Page {users.data.page} sur {users.data.pages}
              </span>
              <Button
                variant="quiet"
                disabled={users.data.page >= users.data.pages}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("page", String(users.data!.page + 1));
                  setParams(next);
                }}
              >
                Suivant
              </Button>
            </nav>
          )}
        </>
      )}
      {action && (
        <div className={styles.modalBackdrop}>
          <section className={styles.modal} role="dialog" aria-modal="true">
            <h2>
              {action === "delete" ? "Supprimer" : "Désactiver"}{" "}
              {selectedItems.length} compte(s) ?
            </h2>
            <form
              className="stack"
              onSubmit={(event) => void applyAction(event)}
            >
              {action === "delete" && (
                <>
                  <div className="form-field">
                    <label htmlFor="user-delete-reason">Motif</label>
                    <textarea
                      id="user-delete-reason"
                      required
                      minLength={3}
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                    />
                  </div>
                  <div className="form-field">
                    <label htmlFor="user-delete-confirm">
                      Saisir SUPPRIMER
                    </label>
                    <input
                      id="user-delete-confirm"
                      required
                      value={confirmation}
                      onChange={(event) => setConfirmation(event.target.value)}
                    />
                  </div>
                </>
              )}
              {mutationError && <p className="error-banner">{mutationError}</p>}
              <div className="cluster">
                <Button variant={action === "delete" ? "danger" : "primary"}>
                  Confirmer
                </Button>
                <Button
                  type="button"
                  variant="quiet"
                  onClick={() => setAction(null)}
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
