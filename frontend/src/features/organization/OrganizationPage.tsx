import { Building2, Save, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  OrganizationAdministration,
  OrganizationGrant,
  OrganizationUnitDetail,
} from "../../lib/api/types";
import { useApi } from "../../lib/useApi";
import styles from "../users/users.module.css";

type UnitForm = {
  id: number | null;
  code: string;
  short_name: string;
  long_name: string;
  kind: string;
  display_order: number;
  parent_id: number | null;
  active: boolean;
  state_token?: string;
};

const EMPTY_UNIT: UnitForm = {
  id: null,
  code: "",
  short_name: "",
  long_name: "",
  kind: "unit",
  display_order: 0,
  parent_id: null,
  active: true,
};

export function OrganizationPage() {
  const organization = useApi<OrganizationAdministration>(
    "/api/v1/organization/",
  );
  const [unit, setUnit] = useState<UnitForm>(EMPTY_UNIT);
  const [grant, setGrant] = useState({
    user_id: "",
    department_id: "",
    role_code: "",
    scope: "tree",
    valid_from: new Date().toISOString().slice(0, 16),
    valid_until: "",
    reason: "",
  });
  const [message, setMessage] = useState("");
  const [mutationError, setMutationError] = useState("");
  useEffect(() => {
    if (!unit.id) return;
    const code = document.getElementById("unit-code");
    code?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    code?.focus();
  }, [unit.id]);
  if (organization.loading)
    return <Skeleton label="Chargement de l’organigramme" />;
  if (organization.error || !organization.data)
    return (
      <ErrorState
        error={organization.error ?? new Error("Organigramme indisponible")}
        retry={() => void organization.reload()}
      />
    );
  const data = organization.data;

  async function saveUnit(event: FormEvent) {
    event.preventDefault();
    setMutationError("");
    try {
      const payload = {
        ...unit,
        reason: unit.id ? "Mise à jour depuis CSRS ENT" : undefined,
      };
      await apiFetch<OrganizationUnitDetail>(
        unit.id
          ? `/api/v1/organization/units/${unit.id}/`
          : "/api/v1/organization/units/",
        { method: unit.id ? "PATCH" : "POST", body: JSON.stringify(payload) },
      );
      setMessage(unit.id ? "Unité mise à jour." : "Unité créée.");
      setUnit(EMPTY_UNIT);
      await organization.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Enregistrement impossible.",
      );
    }
  }

  async function createGrant(event: FormEvent) {
    event.preventDefault();
    setMutationError("");
    try {
      await apiFetch<OrganizationGrant>("/api/v1/organization/grants/", {
        method: "POST",
        body: JSON.stringify({
          ...grant,
          user_id: Number(grant.user_id),
          department_id: Number(grant.department_id),
          valid_from: new Date(grant.valid_from).toISOString(),
          valid_until: grant.valid_until
            ? new Date(grant.valid_until).toISOString()
            : null,
        }),
      });
      setMessage("Délégation attribuée.");
      setGrant({
        ...grant,
        user_id: "",
        department_id: "",
        role_code: "",
        valid_until: "",
        reason: "",
      });
      await organization.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Attribution impossible.",
      );
    }
  }

  async function revoke(item: OrganizationGrant) {
    const reason = window.prompt("Motif de révocation :")?.trim();
    if (!reason) return;
    try {
      await apiFetch(`/api/v1/organization/grants/${item.id}/revoke/`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      setMessage("Délégation révoquée.");
      await organization.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Révocation impossible.",
      );
    }
  }

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Administration IT</p>
          <h1>Organigramme</h1>
          <p>
            Modifiez les unités et délégations dans Odoo. Les cycles et conflits
            sont refusés côté serveur.
          </p>
        </div>
      </header>
      {message && (
        <p className="success-banner" role="status">
          {message}
        </p>
      )}
      {mutationError && (
        <p className="error-banner" role="alert">
          {mutationError}
        </p>
      )}
      <div className="stack">
        <Card>
          <form className="stack" onSubmit={(event) => void saveUnit(event)}>
            <fieldset className={styles.fieldset}>
              <legend>
                <Building2 size={20} aria-hidden="true" />{" "}
                {unit.id ? "Modifier l’unité" : "Nouvelle unité"}
              </legend>
              <div className="form-grid">
                <div className="form-field">
                  <label htmlFor="unit-code">Code</label>
                  <input
                    id="unit-code"
                    required
                    pattern="[A-Za-z0-9_-]+"
                    value={unit.code}
                    onChange={(event) =>
                      setUnit({
                        ...unit,
                        code: event.target.value.toUpperCase(),
                      })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="unit-short">Nom court</label>
                  <input
                    id="unit-short"
                    required
                    value={unit.short_name}
                    onChange={(event) =>
                      setUnit({ ...unit, short_name: event.target.value })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="unit-long">Nom long</label>
                  <input
                    id="unit-long"
                    required
                    value={unit.long_name}
                    onChange={(event) =>
                      setUnit({ ...unit, long_name: event.target.value })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="unit-kind">Type</label>
                  <input
                    id="unit-kind"
                    required
                    value={unit.kind}
                    onChange={(event) =>
                      setUnit({ ...unit, kind: event.target.value })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="unit-parent">Unité parente</label>
                  <select
                    id="unit-parent"
                    value={unit.parent_id ?? ""}
                    onChange={(event) =>
                      setUnit({
                        ...unit,
                        parent_id: event.target.value
                          ? Number(event.target.value)
                          : null,
                      })
                    }
                  >
                    <option value="">Racine</option>
                    {data.units
                      .filter((item) => item.active && item.id !== unit.id)
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.code} — {item.short_name}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="unit-order">Ordre</label>
                  <input
                    id="unit-order"
                    type="number"
                    min={0}
                    value={unit.display_order}
                    onChange={(event) =>
                      setUnit({
                        ...unit,
                        display_order: Number(event.target.value),
                      })
                    }
                  />
                </div>
                <label className={styles.checkboxField}>
                  <input
                    type="checkbox"
                    checked={unit.active}
                    onChange={(event) =>
                      setUnit({ ...unit, active: event.target.checked })
                    }
                  />{" "}
                  Unité active
                </label>
              </div>
            </fieldset>
            <div className="cluster">
              <Button>
                <Save size={18} aria-hidden="true" /> Enregistrer
              </Button>
              {unit.id && (
                <Button
                  type="button"
                  variant="quiet"
                  onClick={() => setUnit(EMPTY_UNIT)}
                >
                  Annuler
                </Button>
              )}
            </div>
          </form>
        </Card>
        {data.units.length ? (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Unité</th>
                  <th>Type</th>
                  <th>Parent</th>
                  <th>État</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.units.map((item) => (
                  <tr key={item.id}>
                    <td data-label="Code">{item.code}</td>
                    <td data-label="Unité">{item.long_name}</td>
                    <td data-label="Type">{item.kind}</td>
                    <td data-label="Parent">
                      {data.units.find(
                        (candidate) => candidate.id === item.parent_id,
                      )?.short_name ?? "Racine"}
                    </td>
                    <td data-label="État">
                      <StatusBadge
                        status={item.active ? "completed" : "rejected"}
                      >
                        {item.active ? "Active" : "Inactive"}
                      </StatusBadge>
                    </td>
                    <td data-label="Action">
                      <Button
                        variant="quiet"
                        onClick={() => setUnit({ ...item })}
                      >
                        Modifier
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="Aucune unité">Créez la première unité.</EmptyState>
        )}
        <Card>
          <form className="stack" onSubmit={(event) => void createGrant(event)}>
            <fieldset className={styles.fieldset}>
              <legend>
                <ShieldCheck size={20} aria-hidden="true" /> Nouvelle délégation
              </legend>
              <div className="form-grid">
                <div className="form-field">
                  <label htmlFor="grant-user">Personne</label>
                  <select
                    id="grant-user"
                    required
                    value={grant.user_id}
                    onChange={(event) =>
                      setGrant({ ...grant, user_id: event.target.value })
                    }
                  >
                    <option value="">Choisir</option>
                    {data.users.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="grant-unit">Unité</label>
                  <select
                    id="grant-unit"
                    required
                    value={grant.department_id}
                    onChange={(event) =>
                      setGrant({ ...grant, department_id: event.target.value })
                    }
                  >
                    <option value="">Choisir</option>
                    {data.units
                      .filter((item) => item.active)
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.code} — {item.short_name}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="grant-role">Rôle</label>
                  <select
                    id="grant-role"
                    required
                    value={grant.role_code}
                    onChange={(event) =>
                      setGrant({ ...grant, role_code: event.target.value })
                    }
                  >
                    <option value="">Choisir</option>
                    {data.role_codes.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="grant-scope">Portée</label>
                  <select
                    id="grant-scope"
                    value={grant.scope}
                    onChange={(event) =>
                      setGrant({ ...grant, scope: event.target.value })
                    }
                  >
                    <option value="unit">Cette unité</option>
                    <option value="tree">Unité et sous-unités</option>
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="grant-from">Valide à partir de</label>
                  <input
                    id="grant-from"
                    type="datetime-local"
                    required
                    value={grant.valid_from}
                    onChange={(event) =>
                      setGrant({ ...grant, valid_from: event.target.value })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="grant-until">Valide jusqu’au</label>
                  <input
                    id="grant-until"
                    type="datetime-local"
                    value={grant.valid_until}
                    onChange={(event) =>
                      setGrant({ ...grant, valid_until: event.target.value })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="grant-reason">Motif</label>
                  <textarea
                    id="grant-reason"
                    required
                    minLength={3}
                    value={grant.reason}
                    onChange={(event) =>
                      setGrant({ ...grant, reason: event.target.value })
                    }
                  />
                </div>
              </div>
            </fieldset>
            <Button>
              <ShieldCheck size={18} aria-hidden="true" /> Attribuer
            </Button>
          </form>
        </Card>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Personne</th>
                <th>Rôle</th>
                <th>Unité</th>
                <th>Portée</th>
                <th>État</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.grants.map((item) => (
                <tr key={item.id}>
                  <td data-label="Personne">{item.user.name}</td>
                  <td data-label="Rôle">{item.role_code}</td>
                  <td data-label="Unité">{item.department.short_name}</td>
                  <td data-label="Portée">
                    {item.scope === "tree" ? "Arborescence" : "Unité"}
                  </td>
                  <td data-label="État">
                    <StatusBadge
                      status={item.active ? "completed" : "rejected"}
                    >
                      {item.active ? "Active" : "Révoquée"}
                    </StatusBadge>
                  </td>
                  <td data-label="Action">
                    {item.active && (
                      <Button variant="quiet" onClick={() => void revoke(item)}>
                        <XCircle size={18} aria-hidden="true" /> Révoquer
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
