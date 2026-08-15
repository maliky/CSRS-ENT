import { KeyRound, Power, PowerOff, Save } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Button,
  ButtonLink,
  Card,
  ErrorState,
  FrenchDateInput,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  ManagedUserDetail,
  TemporaryPasswordResult,
  UserManagementOptions,
} from "../../lib/api/types";
import { useNavigate, useParams } from "../../lib/router";
import { useApi } from "../../lib/useApi";
import styles from "./users.module.css";

type FormState = {
  email: string;
  login_alias: string;
  first_name: string;
  last_name: string;
  position: string;
  phone: string;
  agenda_direction: string;
  include_in_direction_agendas: boolean;
  unit_ids: number[];
  primary_unit_id: number | null;
  primary_supervisor_id: number | null;
  organization_effective_date: string;
};

export function UserFormPage({ mode }: { mode: "create" | "edit" }) {
  const { userId } = useParams();
  const options = useApi<UserManagementOptions>("/api/v1/users/options/");
  const user = useApi<ManagedUserDetail>(
    `/api/v1/users/${userId}/`,
    mode === "edit",
  );
  if (options.loading || (mode === "edit" && user.loading))
    return <Skeleton label="Chargement de la fiche" />;
  if (
    options.error ||
    user.error ||
    !options.data ||
    (mode === "edit" && !user.data)
  )
    return (
      <ErrorState
        error={options.error ?? user.error ?? new Error("Fiche indisponible")}
        retry={() => {
          void options.reload();
          void user.reload();
        }}
      />
    );
  return (
    <UserForm
      key={user.data?.state_token ?? "new"}
      mode={mode}
      options={options.data}
      user={user.data}
      onSaved={user.setData}
    />
  );
}

function UserForm({
  mode,
  options,
  user,
  onSaved,
}: {
  mode: "create" | "edit";
  options: UserManagementOptions;
  user: ManagedUserDetail | null;
  onSaved: (value: ManagedUserDetail) => void;
}) {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>(() => ({
    email: user?.email ?? "",
    login_alias: user?.login_alias ?? "",
    first_name: user?.first_name ?? "",
    last_name: user?.last_name ?? "",
    position: user?.position ?? "",
    phone: user?.phone ?? "",
    agenda_direction: user?.agenda_direction ?? "",
    include_in_direction_agendas: user?.include_in_direction_agendas ?? true,
    unit_ids: user?.unit_ids ?? [],
    primary_unit_id: user?.primary_unit_id ?? null,
    primary_supervisor_id: user?.primary_supervisor?.id ?? null,
    organization_effective_date: options.today,
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [temporaryPassword, setTemporaryPassword] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const saved = await apiFetch<ManagedUserDetail>(
        mode === "create" ? "/api/v1/users/" : `/api/v1/users/${user?.id}/`,
        {
          method: mode === "create" ? "POST" : "PATCH",
          body: JSON.stringify({
            ...form,
            login_alias: form.login_alias || null,
            state_token: user?.state_token,
          }),
        },
      );
      if (mode === "create")
        navigate(`/administration/utilisateurs/${saved.id}`);
      else {
        onSaved(saved);
        setMessage("Compte enregistré.");
      }
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Enregistrement impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function accountAction(
    kind: "deactivate" | "reactivate" | "temporary-password",
  ) {
    if (!user) return;
    setError("");
    if (
      kind === "deactivate" &&
      !window.confirm("Désactiver ce compte en conservant son historique ?")
    )
      return;
    try {
      if (kind === "temporary-password") {
        const result = await apiFetch<TemporaryPasswordResult>(
          `/api/v1/users/${user.id}/temporary-password/`,
          {
            method: "POST",
            body: JSON.stringify({ state_token: user.state_token }),
          },
        );
        setTemporaryPassword(result.temporary_password);
        const refreshed = await apiFetch<ManagedUserDetail>(
          `/api/v1/users/${user.id}/`,
        );
        onSaved(refreshed);
        return;
      }
      const saved = await apiFetch<ManagedUserDetail>(
        `/api/v1/users/${user.id}/${kind}/`,
        {
          method: "POST",
          body: JSON.stringify({ state_token: user.state_token }),
        },
      );
      onSaved(saved);
      setMessage(
        kind === "deactivate" ? "Compte désactivé." : "Compte réactivé.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Action impossible.");
    }
  }

  const selectedUnits = options.units.filter((item) =>
    form.unit_ids.includes(item.id),
  );
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Administration IT</p>
          <h1>{mode === "create" ? "Ajouter une personne" : user?.name}</h1>
          <p>
            Les changements d’unité et de responsable conservent leurs anciennes
            relations.
          </p>
        </div>
        <ButtonLink to="/administration/utilisateurs" variant="quiet">
          Retour
        </ButtonLink>
      </header>
      {message && (
        <p className="success-banner" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <Card>
          <fieldset className={styles.fieldset} disabled={saving}>
            <legend>Identité</legend>
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="first-name">Prénom</label>
                <input
                  id="first-name"
                  value={form.first_name}
                  onChange={(event) =>
                    setForm({ ...form, first_name: event.target.value })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="last-name">Nom</label>
                <input
                  id="last-name"
                  value={form.last_name}
                  onChange={(event) =>
                    setForm({ ...form, last_name: event.target.value })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  required
                  value={form.email}
                  onChange={(event) =>
                    setForm({ ...form, email: event.target.value })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="alias">Identifiant court</label>
                <input
                  id="alias"
                  pattern="[a-z][a-z0-9_-]*"
                  value={form.login_alias}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      login_alias: event.target.value.toLowerCase(),
                    })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="position">Fonction</label>
                <input
                  id="position"
                  value={form.position}
                  onChange={(event) =>
                    setForm({ ...form, position: event.target.value })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="phone">Téléphone</label>
                <input
                  id="phone"
                  value={form.phone}
                  onChange={(event) =>
                    setForm({ ...form, phone: event.target.value })
                  }
                />
              </div>
            </div>
          </fieldset>
        </Card>
        <Card>
          <fieldset className={styles.fieldset} disabled={saving}>
            <legend>Agenda et organigramme</legend>
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="agenda-direction">Direction</label>
                <select
                  id="agenda-direction"
                  value={form.agenda_direction}
                  onChange={(event) =>
                    setForm({ ...form, agenda_direction: event.target.value })
                  }
                >
                  <option value="">Non classée</option>
                  {options.agenda_directions.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <label className={styles.checkboxField}>
                <input
                  type="checkbox"
                  checked={form.include_in_direction_agendas}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      include_in_direction_agendas: event.target.checked,
                    })
                  }
                />{" "}
                Inclure dans les agendas
              </label>
              <div className="form-field">
                <label htmlFor="units">Unités actuelles</label>
                <select
                  id="units"
                  multiple
                  value={form.unit_ids.map(String)}
                  onChange={(event) => {
                    const unit_ids = Array.from(
                      event.currentTarget.selectedOptions,
                      (option) => Number(option.value),
                    );
                    setForm({
                      ...form,
                      unit_ids,
                      primary_unit_id: unit_ids.includes(
                        form.primary_unit_id ?? -1,
                      )
                        ? form.primary_unit_id
                        : null,
                    });
                  }}
                >
                  {options.units.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.code} — {item.short_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="primary-unit">Unité principale</label>
                <select
                  id="primary-unit"
                  value={form.primary_unit_id ?? ""}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      primary_unit_id: event.target.value
                        ? Number(event.target.value)
                        : null,
                      primary_supervisor_id: event.target.value
                        ? form.primary_supervisor_id
                        : null,
                    })
                  }
                >
                  <option value="">Aucune</option>
                  {selectedUnits.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.code} — {item.short_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="supervisor">Responsable principal</label>
                <select
                  id="supervisor"
                  disabled={!form.primary_unit_id}
                  value={form.primary_supervisor_id ?? ""}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      primary_supervisor_id: event.target.value
                        ? Number(event.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">Aucun</option>
                  {options.users
                    .filter((item) => item.id !== user?.id)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} — {item.position || "sans fonction"}
                      </option>
                    ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="effective-date">Date d’effet</label>
                <FrenchDateInput
                  id="effective-date"
                  required
                  value={form.organization_effective_date}
                  onValueChange={(value) =>
                    setForm({ ...form, organization_effective_date: value })
                  }
                />
              </div>
            </div>
          </fieldset>
        </Card>
        <div className="cluster">
          <Button disabled={saving}>
            <Save size={18} aria-hidden="true" />{" "}
            {saving ? "Enregistrement…" : "Enregistrer"}
          </Button>
          <ButtonLink to="/administration/utilisateurs" variant="quiet">
            Annuler
          </ButtonLink>
        </div>
      </form>
      {mode === "edit" && user && (
        <Card className={styles.accessCard}>
          <div>
            <h2>Accès au compte</h2>
            <div className="cluster">
              <StatusBadge status={user.is_active ? "completed" : "rejected"}>
                {user.is_active ? "Actif" : "Inactif"}
              </StatusBadge>
              {user.password_change_required && (
                <StatusBadge status="submitted">
                  Mot de passe à changer
                </StatusBadge>
              )}
            </div>
            {temporaryPassword && (
              <>
                <p>Ce mot de passe n’est affiché qu’ici :</p>
                <code className={styles.temporaryPassword}>
                  {temporaryPassword}
                </code>
              </>
            )}
          </div>
          <div className="cluster">
            {user.capabilities.reset_password && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => void accountAction("temporary-password")}
              >
                <KeyRound size={18} aria-hidden="true" /> Mot de passe
                temporaire
              </Button>
            )}
            {user.capabilities.deactivate && (
              <Button
                type="button"
                variant="danger"
                onClick={() => void accountAction("deactivate")}
              >
                <PowerOff size={18} aria-hidden="true" /> Désactiver
              </Button>
            )}
            {user.capabilities.reactivate && (
              <Button
                type="button"
                onClick={() => void accountAction("reactivate")}
              >
                <Power size={18} aria-hidden="true" /> Réactiver
              </Button>
            )}
          </div>
        </Card>
      )}
    </>
  );
}
