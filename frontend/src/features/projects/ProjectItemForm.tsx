import { useState, type FormEvent } from "react";
import { Button, FrenchDateInput, WorkloadInput } from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  Person,
  ProjectItemValues,
  ResearchProjectDetail,
} from "../../lib/api/types";

export type ProjectResource =
  | "action_plan"
  | "results"
  | "deliverables"
  | "finance"
  | "compliance"
  | "risks"
  | "reports"
  | "closure";

type FieldKind =
  | "text"
  | "textarea"
  | "date"
  | "number"
  | "workload"
  | "boolean"
  | "user"
  | "user-list"
  | "select";

type Field = {
  name: string;
  label: string;
  kind: FieldKind;
  required?: boolean;
  defaultValue?: string | boolean;
  choices?: Array<{ value: string; label: string }>;
};

const RESOURCE_FIELDS: Record<ProjectResource, Field[]> = {
  action_plan: [
    { name: "name", label: "Activité", kind: "text", required: true },
    { name: "description", label: "Description", kind: "textarea" },
    {
      name: "user_ids",
      label: "Responsable",
      kind: "user-list",
      required: true,
    },
    { name: "csrs_start_date", label: "Début", kind: "date", required: true },
    { name: "date_deadline", label: "Échéance", kind: "date", required: true },
    {
      name: "csrs_estimated_work_days",
      label: "Charge estimée",
      kind: "workload",
      required: true,
      defaultValue: "1",
    },
  ],
  results: [
    { name: "name", label: "Résultat", kind: "text", required: true },
    { name: "indicator", label: "Indicateur", kind: "text", required: true },
    { name: "target_value", label: "Cible", kind: "text", required: true },
    { name: "achieved_value", label: "Réalisation", kind: "text" },
  ],
  deliverables: [
    { name: "name", label: "Livrable", kind: "text", required: true },
    { name: "deadline", label: "Échéance", kind: "date" },
    { name: "csrs_version", label: "Version", kind: "text" },
    {
      name: "csrs_at_risk",
      label: "Livrable à risque",
      kind: "boolean",
      defaultValue: false,
    },
  ],
  finance: [
    { name: "code", label: "Code budgétaire", kind: "text", required: true },
    { name: "name", label: "Ligne budgétaire", kind: "text", required: true },
    {
      name: "planned_amount",
      label: "Montant prévu",
      kind: "number",
      required: true,
    },
  ],
  compliance: [
    {
      name: "kind",
      label: "Type",
      kind: "select",
      required: true,
      defaultValue: "ethics",
      choices: [
        { value: "ethics", label: "Éthique" },
        { value: "contract", label: "Contrat" },
        { value: "purchase", label: "Achat" },
        { value: "donor", label: "Obligation bailleur" },
        { value: "other", label: "Autre" },
      ],
    },
    {
      name: "description",
      label: "Exigence",
      kind: "textarea",
      required: true,
    },
    { name: "owner_id", label: "Responsable", kind: "user", required: true },
    { name: "due_date", label: "Échéance", kind: "date" },
  ],
  risks: [
    { name: "title", label: "Risque", kind: "text", required: true },
    { name: "description", label: "Description", kind: "textarea" },
    {
      name: "probability",
      label: "Probabilité (1–5)",
      kind: "number",
      required: true,
      defaultValue: "1",
    },
    {
      name: "impact",
      label: "Impact (1–5)",
      kind: "number",
      required: true,
      defaultValue: "1",
    },
    { name: "owner_id", label: "Responsable", kind: "user", required: true },
    {
      name: "treatment",
      label: "Plan de traitement",
      kind: "textarea",
      required: true,
    },
  ],
  reports: [
    { name: "title", label: "Rapport", kind: "text", required: true },
    {
      name: "report_type",
      label: "Type",
      kind: "select",
      required: true,
      defaultValue: "technical",
      choices: [
        { value: "technical", label: "Technique" },
        { value: "financial", label: "Financier" },
        { value: "final", label: "Final" },
      ],
    },
    {
      name: "period_start",
      label: "Début de période",
      kind: "date",
      required: true,
    },
    {
      name: "period_end",
      label: "Fin de période",
      kind: "date",
      required: true,
    },
    { name: "due_date", label: "Échéance", kind: "date", required: true },
  ],
  closure: [
    { name: "assessment", label: "Bilan", kind: "textarea", required: true },
    {
      name: "equipment_disposition",
      label: "Sort des équipements",
      kind: "textarea",
      required: true,
    },
    {
      name: "data_disposition",
      label: "Sort des données",
      kind: "textarea",
      required: true,
    },
    { name: "final_balance", label: "Solde final", kind: "number" },
    { name: "outlook", label: "Perspectives", kind: "textarea" },
    {
      name: "residual_liabilities",
      label: "Passifs résiduels",
      kind: "textarea",
    },
    {
      name: "sustainability",
      label: "Durabilité",
      kind: "textarea",
      required: true,
    },
  ],
};

function initialValues(fields: Field[], initial?: ProjectItemValues) {
  return Object.fromEntries(
    fields.map((field) => {
      const source = initial?.[field.name];
      const value = Array.isArray(source)
        ? String(source[0] ?? "")
        : source === null || source === undefined
          ? (field.defaultValue ?? "")
          : field.kind === "boolean"
            ? Boolean(source)
            : String(source);
      return [field.name, value];
    }),
  );
}

function rpcValue(
  field: Field,
  value: string | boolean,
): string | number | boolean | number[] {
  if (field.kind === "boolean") return Boolean(value);
  if (
    field.kind === "number" ||
    field.kind === "workload" ||
    field.kind === "user"
  )
    return Number(value);
  if (field.kind === "user-list") return value ? [Number(value)] : [];
  return String(value);
}

export function ProjectItemForm({
  project,
  resource,
  users,
  itemId,
  initial,
  onSaved,
  openLabel = "Ajouter",
}: {
  project: ResearchProjectDetail;
  resource: ProjectResource;
  users: Person[];
  itemId?: number;
  initial?: ProjectItemValues;
  onSaved: () => Promise<void>;
  openLabel?: string;
}) {
  const fields = RESOURCE_FIELDS[resource];
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string | boolean>>(() =>
    initialValues(fields, initial),
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload = Object.fromEntries(
        fields.map((field) => [
          field.name,
          rpcValue(field, values[field.name] ?? ""),
        ]),
      );
      const suffix = itemId ? `${itemId}/` : "";
      await apiFetch(
        `/api/v1/research-projects/${project.id}/items/${resource}/${suffix}`,
        {
          method: itemId ? "PATCH" : "POST",
          body: JSON.stringify({ revision: project.revision, values: payload }),
        },
      );
      setValues(initialValues(fields, initial));
      setOpen(false);
      await onSaved();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Enregistrement impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!open)
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        {itemId ? "Modifier" : openLabel}
      </Button>
    );

  return (
    <form className="stack" onSubmit={(event) => void submit(event)}>
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      <div className="form-grid">
        {fields.map((field) => (
          <div
            className={`form-field ${field.kind === "textarea" ? "wide" : ""}`}
            key={field.name}
          >
            {field.kind !== "workload" && (
              <label htmlFor={`${resource}-${field.name}`}>{field.label}</label>
            )}
            {field.kind === "workload" ? (
              <WorkloadInput
                id={`${resource}-${field.name}`}
                valueDays={String(values[field.name] ?? "")}
                hoursPerDay={8}
                onValueChange={(value) =>
                  setValues({ ...values, [field.name]: value })
                }
              />
            ) : field.kind === "textarea" ? (
              <textarea
                id={`${resource}-${field.name}`}
                required={field.required}
                value={String(values[field.name] ?? "")}
                onChange={(event) =>
                  setValues({ ...values, [field.name]: event.target.value })
                }
              />
            ) : field.kind === "select" ||
              field.kind === "user" ||
              field.kind === "user-list" ? (
              <select
                id={`${resource}-${field.name}`}
                required={field.required}
                value={String(values[field.name] ?? "")}
                onChange={(event) =>
                  setValues({ ...values, [field.name]: event.target.value })
                }
              >
                <option value="">Choisir…</option>
                {(field.kind === "user" || field.kind === "user-list"
                  ? users.map((user) => ({
                      value: String(user.id),
                      label: user.name,
                    }))
                  : (field.choices ?? [])
                ).map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
              </select>
            ) : field.kind === "boolean" ? (
              <input
                id={`${resource}-${field.name}`}
                type="checkbox"
                checked={Boolean(values[field.name])}
                onChange={(event) =>
                  setValues({ ...values, [field.name]: event.target.checked })
                }
              />
            ) : field.kind === "date" ? (
              <FrenchDateInput
                id={`${resource}-${field.name}`}
                required={field.required}
                value={String(values[field.name] ?? "")}
                onValueChange={(value) =>
                  setValues({ ...values, [field.name]: value })
                }
              />
            ) : (
              <input
                id={`${resource}-${field.name}`}
                type={field.kind}
                required={field.required}
                min={field.kind === "number" ? "0" : undefined}
                step={field.kind === "number" ? "any" : undefined}
                value={String(values[field.name] ?? "")}
                onChange={(event) =>
                  setValues({ ...values, [field.name]: event.target.value })
                }
              />
            )}
          </div>
        ))}
      </div>
      <div className="cluster">
        <Button type="submit" disabled={saving}>
          {saving ? "Enregistrement…" : "Enregistrer"}
        </Button>
        <Button type="button" variant="quiet" onClick={() => setOpen(false)}>
          Annuler
        </Button>
      </div>
    </form>
  );
}
