import { ArrowRight, History, Plus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import {
  Button,
  ButtonLink,
  Card,
  ErrorState,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type { ProcedureDetail, ProcedureOptions } from "../../lib/api/types";
import { useParams } from "../../lib/router";
import { useApi } from "../../lib/useApi";

const ACTION_LABELS: Record<string, string> = {
  submit: "Soumettre",
  approve: "Approuver",
  pay: "Confirmer le paiement",
  order: "Créer le bon de commande",
  receive: "Confirmer la livraison",
  invoice: "Enregistrer la facture",
  complete: "Terminer",
  distribute: "Diffuser",
  notify: "Notifier",
  acknowledge: "Accuser réception",
  transmit: "Transmettre",
  audit: "Auditer",
  archive: "Archiver",
  dispose: "Clôturer la conservation",
  correct: "Demander correction",
  reject: "Rejeter",
  resubmit: "Soumettre à nouveau",
};

function confirmationPhrase() {
  return `VALIDÉ LE ${new Intl.DateTimeFormat("fr-FR").format(new Date())}`;
}

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

function money(value: number, currency: string) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function ProcessDetailPage() {
  const { processId = "" } = useParams();
  const process = useApi<ProcedureDetail>(
    `/api/v1/processes/${processId}/`,
    Boolean(processId),
  );
  const options = useApi<ProcedureOptions>(
    "/api/v1/processes/options/",
    process.data?.process_type === "purchase" &&
      process.data.state === "procurement",
  );
  const [mutationError, setMutationError] = useState("");
  const [quotation, setQuotation] = useState({
    vendor_id: "",
    reference: "",
    quotation_date: "",
    amount: "",
  });
  const [quotationDocument, setQuotationDocument] = useState<File | null>(null);
  const [procurement, setProcurement] = useState({
    selected_quotation_id: "",
    product_id: "",
    quantity: "",
    negotiated_amount: "",
  });
  const [evidence, setEvidence] = useState({
    reference: "",
    date: "",
    amount: "",
  });
  const [evidenceDocument, setEvidenceDocument] = useState<File | null>(null);

  useEffect(() => {
    const current = process.data?.presentation;
    if (!current || current.kind !== "purchase") return;
    setProcurement((value) => ({
      selected_quotation_id:
        value.selected_quotation_id ||
        String(current.selected_quotation_id ?? ""),
      product_id: value.product_id || String(current.product?.id ?? ""),
      quantity: value.quantity || String(current.quantity || ""),
      negotiated_amount:
        value.negotiated_amount || String(current.negotiated_amount || ""),
    }));
  }, [process.data]);

  async function transition(action: string) {
    if (!process.data) return;
    setMutationError("");
    let note = "";
    let confirmation = "";
    let stageData: Record<string, unknown> = {};
    if (["correct", "reject"].includes(action)) {
      note = window.prompt("Motif :")?.trim() ?? "";
      if (!note) return;
    }
    if (process.data.state === "dg_review" && action === "approve") {
      confirmation =
        window
          .prompt(`Saisissez exactement : ${confirmationPhrase()}`)
          ?.trim() ?? "";
      if (!confirmation) return;
    }
    try {
      if (process.data.process_type === "fund" && action === "pay") {
        if (!evidence.date)
          throw new Error("La date de paiement est obligatoire.");
        stageData = { payment_date: evidence.date };
      }
      if (
        process.data.process_type === "purchase" &&
        ["receive", "invoice", "pay"].includes(action)
      ) {
        if (!evidence.reference || !evidence.date || !evidenceDocument)
          throw new Error(
            "La référence, la date et le document justificatif sont obligatoires.",
          );
        stageData = {
          reference: evidence.reference,
          date: evidence.date,
          amount: evidence.amount ? Number(evidence.amount) : 0,
          document: await documentPayload(evidenceDocument),
        };
      }
      await apiFetch(`/api/v1/processes/${process.data.id}/transition/`, {
        method: "POST",
        body: JSON.stringify({
          action,
          revision: process.data.revision,
          note,
          confirmation,
          stage_data: stageData,
        }),
      });
      setEvidence({ reference: "", date: "", amount: "" });
      setEvidenceDocument(null);
      await process.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Transition impossible.",
      );
    }
  }

  async function saveQuotation(event: FormEvent) {
    event.preventDefault();
    if (!process.data || !quotationDocument) return;
    setMutationError("");
    try {
      await apiFetch(`/api/v1/processes/${process.data.id}/quotations/`, {
        method: "POST",
        body: JSON.stringify({
          revision: process.data.revision,
          vendor_id: Number(quotation.vendor_id),
          reference: quotation.reference,
          quotation_date: quotation.quotation_date,
          amount: Number(quotation.amount),
          documents: [await documentPayload(quotationDocument)],
        }),
      });
      setQuotation({
        vendor_id: "",
        reference: "",
        quotation_date: "",
        amount: "",
      });
      setQuotationDocument(null);
      await process.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Cotation impossible.",
      );
    }
  }

  async function saveProcurement(event: FormEvent) {
    event.preventDefault();
    if (!process.data) return;
    setMutationError("");
    try {
      await apiFetch(`/api/v1/processes/${process.data.id}/procurement/`, {
        method: "PUT",
        body: JSON.stringify({
          revision: process.data.revision,
          selected_quotation_id: Number(procurement.selected_quotation_id),
          product_id: Number(procurement.product_id),
          quantity: Number(procurement.quantity),
          negotiated_amount: Number(procurement.negotiated_amount),
        }),
      });
      await process.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error
          ? caught.message
          : "Enregistrement des achats impossible.",
      );
    }
  }

  if (process.loading) return <Skeleton label="Chargement du dossier" />;
  if (process.error || !process.data)
    return (
      <ErrorState
        error={process.error ?? new Error("Dossier indisponible")}
        retry={() => void process.reload()}
      />
    );
  const data = process.data;
  const presentation = data.presentation;
  const purchase = presentation?.kind === "purchase" ? presentation : null;
  const fund = presentation?.kind === "fund" ? presentation : null;
  const evidenceAction = data.available_actions.find((action) =>
    ["receive", "invoice", "pay"].includes(action),
  );

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">{data.reference}</p>
          <h1>{data.subject}</h1>
          <p>{data.process_type_label}</p>
        </div>
        <ButtonLink variant="quiet" to="/procedures">
          Retour aux procédures
        </ButtonLink>
      </header>
      {mutationError && (
        <p className="error-banner" role="alert">
          {mutationError}
        </p>
      )}
      <Card>
        <div className="cluster">
          <StatusBadge status={data.state}>{data.state_label}</StatusBadge>
          <span>Demandeur : {data.requester.name}</span>
          <span>Unité : {data.origin_department.name}</span>
        </div>
        <p>{data.description}</p>
        {data.correction_reason && (
          <p className="error-banner">{data.correction_reason}</p>
        )}
        {evidenceAction && (
          <div className="form-grid">
            {data.process_type === "fund" ? (
              <div className="form-field">
                <label htmlFor="process-payment-date">Date de paiement</label>
                <input
                  id="process-payment-date"
                  type="date"
                  value={evidence.date}
                  onChange={(event) =>
                    setEvidence({ ...evidence, date: event.target.value })
                  }
                />
              </div>
            ) : (
              <>
                <div className="form-field">
                  <label htmlFor="evidence-reference">
                    Référence du justificatif
                  </label>
                  <input
                    id="evidence-reference"
                    value={evidence.reference}
                    onChange={(event) =>
                      setEvidence({
                        ...evidence,
                        reference: event.target.value,
                      })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="evidence-date">Date du justificatif</label>
                  <input
                    id="evidence-date"
                    type="date"
                    value={evidence.date}
                    onChange={(event) =>
                      setEvidence({ ...evidence, date: event.target.value })
                    }
                  />
                </div>
                {evidenceAction !== "receive" && (
                  <div className="form-field">
                    <label htmlFor="evidence-amount">Montant</label>
                    <input
                      id="evidence-amount"
                      type="number"
                      min="1"
                      value={evidence.amount}
                      onChange={(event) =>
                        setEvidence({ ...evidence, amount: event.target.value })
                      }
                    />
                  </div>
                )}
                <div className="form-field wide">
                  <label htmlFor="evidence-document">
                    Document justificatif
                  </label>
                  <input
                    id="evidence-document"
                    type="file"
                    accept="application/pdf,image/jpeg,image/png"
                    onChange={(event) =>
                      setEvidenceDocument(event.target.files?.[0] ?? null)
                    }
                  />
                </div>
              </>
            )}
          </div>
        )}
        <div className="cluster">
          {data.available_actions.map((action) => (
            <Button
              key={action}
              variant={action === "reject" ? "danger" : "primary"}
              onClick={() => void transition(action)}
            >
              {ACTION_LABELS[action] ?? action} <ArrowRight size={17} />
            </Button>
          ))}
        </div>
      </Card>

      {data.state === "procurement" && purchase && (
        <div className="grid">
          <Card>
            <h2>
              <Plus size={20} /> Ajouter une cotation
            </h2>
            <form
              className="stack"
              onSubmit={(event) => void saveQuotation(event)}
            >
              <label htmlFor="quotation-vendor">Fournisseur</label>
              <select
                id="quotation-vendor"
                required
                value={quotation.vendor_id}
                onChange={(event) =>
                  setQuotation({ ...quotation, vendor_id: event.target.value })
                }
              >
                <option value="">Choisir</option>
                {(options.data?.vendors ?? []).map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.name}
                  </option>
                ))}
              </select>
              <label htmlFor="quotation-reference">
                Référence de la cotation
              </label>
              <input
                id="quotation-reference"
                required
                value={quotation.reference}
                onChange={(event) =>
                  setQuotation({ ...quotation, reference: event.target.value })
                }
              />
              <label htmlFor="quotation-date">Date de la cotation</label>
              <input
                id="quotation-date"
                type="date"
                required
                value={quotation.quotation_date}
                onChange={(event) =>
                  setQuotation({
                    ...quotation,
                    quotation_date: event.target.value,
                  })
                }
              />
              <label htmlFor="quotation-amount">Montant proposé</label>
              <input
                id="quotation-amount"
                type="number"
                min="1"
                required
                value={quotation.amount}
                onChange={(event) =>
                  setQuotation({ ...quotation, amount: event.target.value })
                }
              />
              <label htmlFor="quotation-document">Document de cotation</label>
              <input
                id="quotation-document"
                type="file"
                required
                accept="application/pdf,image/jpeg,image/png"
                onChange={(event) =>
                  setQuotationDocument(event.target.files?.[0] ?? null)
                }
              />
              <Button type="submit">Enregistrer la cotation</Button>
            </form>
          </Card>
          <Card>
            <h2>Préparer le bon de commande</h2>
            <form
              className="stack"
              onSubmit={(event) => void saveProcurement(event)}
            >
              <label htmlFor="selected-quotation">Cotation retenue</label>
              <select
                id="selected-quotation"
                required
                value={procurement.selected_quotation_id}
                onChange={(event) =>
                  setProcurement({
                    ...procurement,
                    selected_quotation_id: event.target.value,
                  })
                }
              >
                <option value="">Choisir</option>
                {purchase.quotations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.vendor.name} · {item.reference} ·{" "}
                    {money(item.amount, data.currency)}
                  </option>
                ))}
              </select>
              <label htmlFor="procurement-product">Produit ou service</label>
              <select
                id="procurement-product"
                required
                value={procurement.product_id}
                onChange={(event) =>
                  setProcurement({
                    ...procurement,
                    product_id: event.target.value,
                  })
                }
              >
                <option value="">Choisir</option>
                {(options.data?.products ?? []).map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
              <label htmlFor="procurement-quantity">Quantité confirmée</label>
              <input
                id="procurement-quantity"
                type="number"
                min="0.000001"
                step="any"
                required
                value={procurement.quantity}
                onChange={(event) =>
                  setProcurement({
                    ...procurement,
                    quantity: event.target.value,
                  })
                }
              />
              <label htmlFor="negotiated-amount">Montant négocié</label>
              <input
                id="negotiated-amount"
                type="number"
                min="1"
                required
                value={procurement.negotiated_amount}
                onChange={(event) =>
                  setProcurement({
                    ...procurement,
                    negotiated_amount: event.target.value,
                  })
                }
              />
              <Button type="submit">
                Enregistrer les informations d'achat
              </Button>
            </form>
          </Card>
        </div>
      )}

      <div className="grid">
        <Card>
          <h2>Données du formulaire</h2>
          {fund ? (
            <dl className="stack">
              <div>
                <dt className="muted">Projet</dt>
                <dd>{data.project?.name ?? "—"}</dd>
              </div>
              <div>
                <dt className="muted">Ligne budgétaire</dt>
                <dd>
                  {fund.budget_line.code} · {fund.budget_line.name}
                </dd>
              </div>
              <div>
                <dt className="muted">Bénéficiaire</dt>
                <dd>{fund.beneficiary.name}</dd>
              </div>
              <div>
                <dt className="muted">Objet</dt>
                <dd>{fund.purpose}</dd>
              </div>
              <div>
                <dt className="muted">Montant</dt>
                <dd>{money(data.amount, data.currency)}</dd>
              </div>
              <div>
                <dt className="muted">Mode de paiement</dt>
                <dd>{fund.payment_method_label}</dd>
              </div>
              <div>
                <dt className="muted">Date de paiement</dt>
                <dd>{fund.payment_date ?? "—"}</dd>
              </div>
              <div>
                <dt className="muted">Pièces jointes</dt>
                <dd>
                  {fund.documents.map((item) => item.name).join(", ") || "—"}
                </dd>
              </div>
            </dl>
          ) : purchase ? (
            <dl className="stack">
              <div>
                <dt className="muted">Projet</dt>
                <dd>{data.project?.name ?? "—"}</dd>
              </div>
              <div>
                <dt className="muted">Ligne budgétaire</dt>
                <dd>
                  {purchase.budget_line.code} · {purchase.budget_line.name}
                </dd>
              </div>
              <div>
                <dt className="muted">Quantité</dt>
                <dd>{purchase.quantity}</dd>
              </div>
              <div>
                <dt className="muted">Montant estimé</dt>
                <dd>{money(purchase.estimated_amount, data.currency)}</dd>
              </div>
              <div>
                <dt className="muted">Fournisseur retenu</dt>
                <dd>{purchase.vendor?.name ?? "—"}</dd>
              </div>
              <div>
                <dt className="muted">Produit ou service</dt>
                <dd>{purchase.product?.name ?? "—"}</dd>
              </div>
              <div>
                <dt className="muted">Montant négocié</dt>
                <dd>
                  {purchase.negotiated_amount
                    ? money(purchase.negotiated_amount, data.currency)
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="muted">Bon de commande</dt>
                <dd>{purchase.purchase_order?.name ?? "—"}</dd>
              </div>
              <div>
                <dt className="muted">Cotations</dt>
                <dd>
                  {purchase.quotations
                    .map((item) => `${item.vendor.name} · ${item.reference}`)
                    .join(", ") || "—"}
                </dd>
              </div>
              <div>
                <dt className="muted">Livraison, facture et paiement</dt>
                <dd>
                  {purchase.evidence
                    .map((item) => `${item.kind} · ${item.reference}`)
                    .join(", ") || "—"}
                </dd>
              </div>
            </dl>
          ) : (
            <dl className="stack">
              {Object.entries(data.details).map(([name, value]) => (
                <div key={name}>
                  <dt className="muted">{name.replaceAll("_", " ")}</dt>
                  <dd>{String(value ?? "—")}</dd>
                </div>
              ))}
            </dl>
          )}
        </Card>
        <Card>
          <h2>
            <History size={20} /> Historique audité
          </h2>
          <ol className="stack">
            {data.events.map((event) => (
              <li key={event.id}>
                <strong>{ACTION_LABELS[event.action] ?? event.action}</strong>
                <br />
                <span className="muted">
                  {event.actor.name} ·{" "}
                  {new Date(event.occurred_at).toLocaleString("fr-FR")}
                </span>
                {event.note && <p>{event.note}</p>}
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </>
  );
}
