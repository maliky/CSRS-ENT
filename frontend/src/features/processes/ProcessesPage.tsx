import { FileCheck2, Plus } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import {
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  ProcedureDetail,
  ProcedureOptions,
  ProcedureSummary,
} from "../../lib/api/types";
import { useApi } from "../../lib/useApi";

type ProcessList = { items: ProcedureSummary[] };
type DetailForm = Record<string, string | boolean>;

const EMPTY_DETAILS: DetailForm = {};

function documentPayload(file: File) {
  return new Promise<{
    name: string;
    mimetype: string;
    content_base64: string;
  }>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Lecture du document impossible."));
    reader.onload = () => {
      const content = String(reader.result ?? "").split(",", 2)[1];
      if (!content) reject(new Error("Document vide ou invalide."));
      else
        resolve({
          name: file.name,
          mimetype: file.type,
          content_base64: content,
        });
    };
    reader.readAsDataURL(file);
  });
}

export function ProcessesPage() {
  const processes = useApi<ProcessList>("/api/v1/processes/");
  const options = useApi<ProcedureOptions>("/api/v1/processes/options/");
  const [showForm, setShowForm] = useState(false);
  const [common, setCommon] = useState({
    process_type: "mission",
    origin_department_id: "",
    project_id: "",
    subject: "",
    description: "",
    amount: "0",
  });
  const [details, setDetails] = useState<DetailForm>(EMPTY_DETAILS);
  const [proof, setProof] = useState<File | null>(null);
  const [mutationError, setMutationError] = useState("");
  const selectedProject = options.data?.projects.find(
    (item) => item.id === Number(common.project_id),
  );

  const defaultDepartment = useMemo(
    () =>
      options.data?.default_department_id ??
      options.data?.departments[0]?.id ??
      null,
    [options.data],
  );

  function detail(name: string, value: string | boolean) {
    setDetails((current) => ({ ...current, [name]: value }));
  }

  function normalizedDetails() {
    const values: Record<string, string | number | boolean> = { ...details };
    const numeric = [
      "budget_line_id",
      "activity_task_id",
      "beneficiary_id",
      "vendor_id",
      "product_id",
      "employee_id",
      "interim_user_id",
      "quantity",
      "estimated_amount",
    ];
    for (const name of numeric) {
      if (typeof values[name] === "string" && values[name] !== "")
        values[name] = Number(values[name]);
      else delete values[name];
    }
    return values;
  }

  async function createProcess(event: FormEvent) {
    event.preventDefault();
    setMutationError("");
    try {
      const documents = proof ? [await documentPayload(proof)] : [];
      await apiFetch<ProcedureDetail>("/api/v1/processes/", {
        method: "POST",
        body: JSON.stringify({
          ...common,
          origin_department_id: Number(
            common.origin_department_id || defaultDepartment,
          ),
          project_id: common.project_id ? Number(common.project_id) : null,
          amount: Number(common.amount || 0),
          details: normalizedDetails(),
          documents,
        }),
      });
      setCommon({
        process_type: "mission",
        origin_department_id: "",
        project_id: "",
        subject: "",
        description: "",
        amount: "0",
      });
      setDetails(EMPTY_DETAILS);
      setProof(null);
      setShowForm(false);
      await processes.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Création impossible.",
      );
    }
  }

  if (processes.loading || options.loading)
    return <Skeleton label="Chargement des procédures" />;
  if (processes.error || !processes.data || options.error || !options.data)
    return (
      <ErrorState
        error={
          processes.error ??
          options.error ??
          new Error("Procédures indisponibles")
        }
        retry={() => {
          void processes.reload();
          void options.reload();
        }}
      />
    );

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Procédures métier</p>
          <h1>Dossiers et visas</h1>
          <p>
            Sorties de fonds, achats, absences, missions, paiements, visas et
            gestion des données suivent leurs circuits audités dans Odoo.
          </p>
        </div>
        <Button onClick={() => setShowForm((current) => !current)}>
          <Plus size={18} /> Nouveau dossier
        </Button>
      </header>
      {showForm && (
        <Card>
          <form
            className="stack"
            onSubmit={(event) => void createProcess(event)}
          >
            <h2>Nouveau dossier</h2>
            {mutationError && (
              <p className="error-banner" role="alert">
                {mutationError}
              </p>
            )}
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="process-type">Procédure</label>
                <select
                  id="process-type"
                  value={common.process_type}
                  onChange={(event) => {
                    setCommon({ ...common, process_type: event.target.value });
                    setDetails(EMPTY_DETAILS);
                    setProof(null);
                  }}
                >
                  {options.data.process_types.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="process-unit">Unité d’origine</label>
                <select
                  id="process-unit"
                  required
                  value={common.origin_department_id || defaultDepartment || ""}
                  onChange={(event) =>
                    setCommon({
                      ...common,
                      origin_department_id: event.target.value,
                    })
                  }
                >
                  {options.data.departments.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field wide">
                <label htmlFor="process-subject">Objet</label>
                <input
                  id="process-subject"
                  required
                  value={common.subject}
                  onChange={(event) =>
                    setCommon({ ...common, subject: event.target.value })
                  }
                />
              </div>
              <div className="form-field wide">
                <label htmlFor="process-description">Description</label>
                <textarea
                  id="process-description"
                  required
                  value={common.description}
                  onChange={(event) =>
                    setCommon({ ...common, description: event.target.value })
                  }
                />
              </div>
              {(["fund", "purchase"] as string[]).includes(
                common.process_type,
              ) && (
                <div className="form-field">
                  <label htmlFor="process-project">Projet</label>
                  <select
                    id="process-project"
                    required
                    value={common.project_id}
                    onChange={(event) =>
                      setCommon({ ...common, project_id: event.target.value })
                    }
                  >
                    <option value="">Choisir…</option>
                    {options.data.projects.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.reference} — {item.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {(["fund", "purchase"] as string[]).includes(
                common.process_type,
              ) && (
                <div className="form-field">
                  <label htmlFor="process-budget">Ligne budgétaire</label>
                  <select
                    id="process-budget"
                    required
                    value={String(details.budget_line_id ?? "")}
                    onChange={(event) =>
                      detail("budget_line_id", event.target.value)
                    }
                  >
                    <option value="">Choisir…</option>
                    {selectedProject?.budget_lines.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.code} — {item.name} ({item.available_amount})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <ProcessSpecificFields
                processType={common.process_type}
                details={details}
                people={options.data.people}
                proof={proof}
                setProof={setProof}
                setDetail={detail}
              />
              {common.process_type === "fund" && (
                <div className="form-field">
                  <label htmlFor="process-amount">Montant demandé</label>
                  <input
                    id="process-amount"
                    type="number"
                    min="1"
                    step="0.01"
                    required
                    value={common.amount}
                    onChange={(event) =>
                      setCommon({ ...common, amount: event.target.value })
                    }
                  />
                </div>
              )}
            </div>
            <div className="cluster">
              <Button type="submit">Créer le brouillon</Button>
              <Button
                type="button"
                variant="quiet"
                onClick={() => setShowForm(false)}
              >
                Annuler
              </Button>
            </div>
          </form>
        </Card>
      )}
      {!processes.data.items.length ? (
        <EmptyState title="Aucun dossier">
          Créez un dossier pour démarrer une procédure.
        </EmptyState>
      ) : (
        <div className="grid">
          {processes.data.items.map((item) => (
            <Card key={item.id}>
              <div className="cluster">
                <FileCheck2 aria-hidden="true" />
                <StatusBadge status={item.state}>
                  {item.state_label}
                </StatusBadge>
              </div>
              <p className="eyebrow">{item.reference}</p>
              <h2>{item.subject}</h2>
              <p>{item.process_type_label}</p>
              <p className="muted">Demandeur : {item.requester.name}</p>
              <ButtonLink variant="secondary" to={`/procedures/${item.id}`}>
                Ouvrir le dossier
              </ButtonLink>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

function ProcessSpecificFields({
  processType,
  details,
  people,
  proof,
  setProof,
  setDetail,
}: {
  processType: string;
  details: DetailForm;
  people: ProcedureOptions["people"];
  proof: File | null;
  setProof: (file: File | null) => void;
  setDetail: (name: string, value: string | boolean) => void;
}) {
  const input = (
    name: string,
    label: string,
    type = "text",
    required = true,
  ) => (
    <div className="form-field" key={name}>
      <label htmlFor={`process-${name}`}>{label}</label>
      <input
        id={`process-${name}`}
        type={type}
        required={required}
        value={String(details[name] ?? "")}
        onChange={(event) => setDetail(name, event.target.value)}
      />
    </div>
  );
  const person = (
    name: string,
    label: string,
    value: "user" | "employee" | "partner",
  ) => (
    <div className="form-field" key={name}>
      <label htmlFor={`process-${name}`}>{label}</label>
      <select
        id={`process-${name}`}
        required
        value={String(details[name] ?? "")}
        onChange={(event) => setDetail(name, event.target.value)}
      >
        <option value="">Choisir…</option>
        {people.map((item) => (
          <option
            key={item.id}
            value={
              value === "employee"
                ? item.employee_id
                : value === "partner"
                  ? item.partner_id
                  : item.id
            }
          >
            {item.name}
          </option>
        ))}
      </select>
    </div>
  );

  if (processType === "fund")
    return (
      <>
        {person("beneficiary_id", "Bénéficiaire", "partner")}
        {input("purpose", "Objet de la dépense")}
        <label className="cluster">
          <input
            type="checkbox"
            checked={Boolean(details.requires_purchase)}
            onChange={(event) =>
              setDetail("requires_purchase", event.target.checked)
            }
          />
          Achat nécessaire
        </label>
      </>
    );
  if (processType === "purchase")
    return (
      <>
        {input("estimated_amount", "Montant estimé", "number")}
        {input("quantity", "Quantité", "number")}
      </>
    );
  if (processType === "absence")
    return (
      <>
        {person("employee_id", "Agent", "employee")}
        {person("interim_user_id", "Intérimaire", "user")}
        {input("start_date", "Début", "date")}
        {input("end_date", "Fin", "date")}
        {input("emergency_contact", "Contact d’urgence")}
        {input("destination", "Destination", "text", false)}
        {input("service", "Service", "text", false)}
      </>
    );
  if (processType === "mission")
    return (
      <>
        {input("destination", "Destination")}
        {input("purpose", "Objet de la mission")}
        {input("departure_date", "Départ", "date")}
        {input("return_date", "Retour", "date")}
        {input("transport_mode", "Mode de transport", "text", false)}
        <label className="cluster">
          <input
            type="checkbox"
            checked={Boolean(details.vehicle_required)}
            onChange={(event) =>
              setDetail("vehicle_required", event.target.checked)
            }
          />
          Véhicule requis
        </label>
      </>
    );
  if (processType === "payment_notice")
    return (
      <>
        <div className="form-field">
          <label htmlFor="process-payment-nature">Nature du paiement</label>
          <select
            id="process-payment-nature"
            required
            value={String(details.payment_nature ?? "")}
            onChange={(event) =>
              setDetail("payment_nature", event.target.value)
            }
          >
            <option value="">Choisir…</option>
            <option value="salary">Salaire</option>
            <option value="honorarium">Honoraire</option>
            <option value="mission">Mission</option>
            <option value="field">Terrain</option>
            <option value="other">Autre</option>
          </select>
        </div>
        {input("payment_date", "Date du paiement", "date")}
        {input("sender", "Émetteur")}
        {input("sending_bank", "Banque émettrice", "text", false)}
        {input("receiving_bank", "Banque destinataire", "text", false)}
        {input("check_number", "Numéro de chèque", "text", false)}
        <div className="form-field wide">
          <label htmlFor="process-proof">Preuve PDF ou image</label>
          <input
            id="process-proof"
            type="file"
            required
            accept="application/pdf,image/jpeg,image/png"
            onChange={(event) => setProof(event.target.files?.[0] ?? null)}
          />
          {proof && <small>{proof.name}</small>}
        </div>
      </>
    );
  if (processType === "visa")
    return (
      <>
        {input("visitor_name", "Nom du visiteur")}
        {input("nationality", "Nationalité")}
        {input("passport_number", "Numéro de passeport")}
        <div className="form-field">
          <label htmlFor="process-visa-kind">Demande</label>
          <select
            id="process-visa-kind"
            required
            value={String(details.visa_kind ?? "")}
            onChange={(event) => setDetail("visa_kind", event.target.value)}
          >
            <option value="">Choisir…</option>
            <option value="new">Nouveau visa</option>
            <option value="extension">Prolongation</option>
          </select>
        </div>
        {input("desired_start_date", "Début souhaité", "date")}
        {input("desired_end_date", "Fin souhaitée", "date")}
        {input("mae_reference", "Référence MAE", "text", false)}
      </>
    );
  return (
    <>
      {input("study_objectives", "Objectifs de l’étude")}
      {input("management_plan", "Plan de gestion")}
      <div className="form-field">
        <label htmlFor="process-classification">Classification</label>
        <select
          id="process-classification"
          required
          value={String(details.classification ?? "")}
          onChange={(event) => setDetail("classification", event.target.value)}
        >
          <option value="">Choisir…</option>
          <option value="public">Public</option>
          <option value="internal">Interne</option>
          <option value="sensitive">Sensible</option>
        </select>
      </div>
      {input("storage_location", "Emplacement de stockage")}
      {input("retention_until", "Conservation jusqu’au", "date")}
      <label className="cluster">
        <input
          type="checkbox"
          checked={Boolean(details.legal_hold)}
          onChange={(event) => setDetail("legal_hold", event.target.checked)}
        />
        Conservation légale
      </label>
      {Boolean(details.legal_hold) && input("legal_hold_reason", "Motif")}
    </>
  );
}
