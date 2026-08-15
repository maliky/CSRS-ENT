import { ArrowRight, History } from "lucide-react";
import { useState } from "react";
import {
  Button,
  ButtonLink,
  Card,
  ErrorState,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type { ProcedureDetail } from "../../lib/api/types";
import { useParams } from "../../lib/router";
import { useApi } from "../../lib/useApi";

const ACTION_LABELS: Record<string, string> = {
  submit: "Soumettre",
  approve: "Approuver",
  pay: "Confirmer le paiement",
  order: "Commander",
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

export function ProcessDetailPage() {
  const { processId = "" } = useParams();
  const process = useApi<ProcedureDetail>(
    `/api/v1/processes/${processId}/`,
    Boolean(processId),
  );
  const [mutationError, setMutationError] = useState("");

  async function transition(action: string) {
    if (!process.data) return;
    let note = "";
    let confirmation = "";
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
      await apiFetch(`/api/v1/processes/${process.data.id}/transition/`, {
        method: "POST",
        body: JSON.stringify({
          action,
          revision: process.data.revision,
          note,
          confirmation,
        }),
      });
      await process.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Transition impossible.",
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
      <div className="grid">
        <Card>
          <h2>Données du formulaire</h2>
          <dl className="stack">
            {Object.entries(data.details).map(([name, value]) => (
              <div key={name}>
                <dt className="muted">{name.replaceAll("_", " ")}</dt>
                <dd>{String(value ?? "—")}</dd>
              </div>
            ))}
          </dl>
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
