import { CheckCircle2, RotateCcw, ShieldCheck } from "lucide-react";
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
  Partner,
  ProjectItemValues,
  ProjectSection,
  ResearchProjectDetail,
} from "../../lib/api/types";
import { useApi } from "../../lib/useApi";
import { useParams } from "../../lib/router";
import { ProjectItemForm, type ProjectResource } from "./ProjectItemForm";

function confirmationPhrase() {
  return `VALIDÉ LE ${new Intl.DateTimeFormat("fr-FR").format(new Date())}`;
}

export function ResearchProjectDetailPage() {
  const { projectId = "" } = useParams();
  const project = useApi<ResearchProjectDetail>(
    `/api/v1/research-projects/${projectId}/`,
    Boolean(projectId),
  );
  const options = useApi<{
    users: ResearchProjectDetail["team"];
    partners: Partner[];
  }>("/api/v1/research-projects/options/");
  const [mutationError, setMutationError] = useState("");
  const [editForm, setEditForm] = useState<null | {
    name: string;
    objectives: string;
    institutional_commitments: string;
    date_start: string;
    date_end: string;
    donor_id: string;
    partner_ids: number[];
    team_user_ids: number[];
  }>(null);

  function beginEdit() {
    if (!project.data) return;
    setEditForm({
      name: project.data.name,
      objectives: project.data.objectives,
      institutional_commitments: project.data.institutional_commitments,
      date_start: project.data.date_start ?? "",
      date_end: project.data.date_end ?? "",
      donor_id: project.data.donor ? String(project.data.donor.id) : "",
      partner_ids: project.data.partners.map((partner) => partner.id),
      team_user_ids: project.data.team.map((user) => user.id),
    });
  }

  async function updateProject(event: FormEvent) {
    event.preventDefault();
    if (!project.data || !editForm) return;
    setMutationError("");
    try {
      await apiFetch(`/api/v1/research-projects/${project.data.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          ...editForm,
          revision: project.data.revision,
          date_start: editForm.date_start || null,
          date_end: editForm.date_end || null,
          donor_id: editForm.donor_id ? Number(editForm.donor_id) : null,
        }),
      });
      setEditForm(null);
      await project.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Modification impossible.",
      );
    }
  }

  async function transition(action: "approve" | "reject" | "close") {
    if (!project.data) return;
    const reason =
      action === "reject" ? window.prompt("Motif du rejet :")?.trim() : "";
    if (action === "reject" && !reason) return;
    try {
      await apiFetch(
        `/api/v1/research-projects/${project.data.id}/transition/`,
        {
          method: "POST",
          body: JSON.stringify({
            action,
            revision: project.data.revision,
            lead_id: action === "approve" ? project.data.proposer.id : null,
            reason: reason ?? "",
          }),
        },
      );
      await project.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Transition impossible.",
      );
    }
  }

  async function sectionTransition(section: ProjectSection, action: string) {
    if (!project.data) return;
    let reason = "";
    let confirmation = "";
    if (action === "correct") {
      reason = window.prompt("Correction demandée :")?.trim() ?? "";
      if (!reason) return;
    }
    if (action === "validate") {
      confirmation =
        window
          .prompt(`Saisissez exactement : ${confirmationPhrase()}`)
          ?.trim() ?? "";
      if (!confirmation) return;
    }
    try {
      await apiFetch(
        `/api/v1/research-projects/${project.data.id}/sections/${section.id}/transition/`,
        {
          method: "POST",
          body: JSON.stringify({
            action,
            revision: section.revision,
            reason,
            confirmation,
          }),
        },
      );
      await project.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Transition impossible.",
      );
    }
  }

  if (project.loading) return <Skeleton label="Chargement du projet" />;
  if (project.error || !project.data)
    return (
      <ErrorState
        error={project.error ?? new Error("Projet indisponible")}
        retry={() => void project.reload()}
      />
    );
  const data = project.data;

  function openDraft(code: string) {
    document
      .getElementById(`project-section-${code}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">{data.reference}</p>
          <h1>{data.name}</h1>
          <p>{data.objectives}</p>
        </div>
        <ButtonLink variant="quiet" to="/projets">
          Retour aux projets
        </ButtonLink>
      </header>
      {mutationError && (
        <p className="error-banner" role="alert">
          {mutationError}
        </p>
      )}
      <Card id="project-section-project">
        <div className="cluster">
          {data.capabilities.edit && !editForm && (
            <Button variant="secondary" onClick={beginEdit}>
              Modifier la fiche projet
            </Button>
          )}
          <StatusBadge status={data.state}>{data.state_label}</StatusBadge>
          <span>Proposé par {data.proposer.name}</span>
          {data.lead && <span>Chef de projet : {data.lead.name}</span>}
        </div>
        {data.institutional_commitments && (
          <p>{data.institutional_commitments}</p>
        )}
        <div className="cluster">
          {data.capabilities.approve && (
            <Button onClick={() => void transition("approve")}>
              <ShieldCheck size={18} /> Autoriser et nommer le proposant
            </Button>
          )}
          {data.capabilities.reject && (
            <Button variant="danger" onClick={() => void transition("reject")}>
              Rejeter
            </Button>
          )}
          {data.capabilities.close && (
            <Button onClick={() => void transition("close")}>Clôturer</Button>
          )}
        </div>
      </Card>
      {editForm && (
        <Card>
          <form
            className="stack"
            onSubmit={(event) => void updateProject(event)}
          >
            <h2>Modifier la fiche projet</h2>
            <div className="form-grid">
              <div className="form-field wide">
                <label htmlFor="edit-project-name">Intitulé</label>
                <input
                  id="edit-project-name"
                  required
                  value={editForm.name}
                  onChange={(event) =>
                    setEditForm({ ...editForm, name: event.target.value })
                  }
                />
              </div>
              <div className="form-field wide">
                <label htmlFor="edit-project-objectives">Objectifs</label>
                <textarea
                  id="edit-project-objectives"
                  required
                  value={editForm.objectives}
                  onChange={(event) =>
                    setEditForm({ ...editForm, objectives: event.target.value })
                  }
                />
              </div>
              <div className="form-field wide">
                <label htmlFor="edit-project-commitments">
                  Engagements institutionnels
                </label>
                <textarea
                  id="edit-project-commitments"
                  value={editForm.institutional_commitments}
                  onChange={(event) =>
                    setEditForm({
                      ...editForm,
                      institutional_commitments: event.target.value,
                    })
                  }
                />
                <small className="muted">
                  Ex. : CSRS met le laboratoire et le personnel à disposition ;
                  l’université partenaire facilite l’accès au terrain.
                </small>
              </div>
              <div className="form-field">
                <label htmlFor="edit-project-donor">Bailleur</label>
                <select
                  id="edit-project-donor"
                  value={editForm.donor_id}
                  onChange={(event) =>
                    setEditForm({ ...editForm, donor_id: event.target.value })
                  }
                >
                  <option value="">Aucun bailleur</option>
                  {(options.data?.partners ?? []).map((partner) => (
                    <option key={partner.id} value={partner.id}>
                      {partner.name}
                    </option>
                  ))}
                </select>
                <small className="muted">
                  Les organisations sont créées par l’administration IT.
                </small>
              </div>
              <div className="form-field">
                <label htmlFor="edit-project-partners">Partenaires</label>
                <select
                  id="edit-project-partners"
                  multiple
                  value={editForm.partner_ids.map(String)}
                  onChange={(event) =>
                    setEditForm({
                      ...editForm,
                      partner_ids: Array.from(
                        event.currentTarget.selectedOptions,
                        (option) => Number(option.value),
                      ),
                    })
                  }
                >
                  {(options.data?.partners ?? []).map((partner) => (
                    <option key={partner.id} value={partner.id}>
                      {partner.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="edit-project-start">Début</label>
                <FrenchDateInput
                  id="edit-project-start"
                  value={editForm.date_start}
                  onValueChange={(dateStart) =>
                    setEditForm({ ...editForm, date_start: dateStart })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="edit-project-end">Fin</label>
                <FrenchDateInput
                  id="edit-project-end"
                  value={editForm.date_end}
                  onValueChange={(dateEnd) =>
                    setEditForm({ ...editForm, date_end: dateEnd })
                  }
                />
              </div>
              <div className="form-field wide">
                <label htmlFor="edit-project-team">Équipe</label>
                <select
                  id="edit-project-team"
                  multiple
                  value={editForm.team_user_ids.map(String)}
                  onChange={(event) =>
                    setEditForm({
                      ...editForm,
                      team_user_ids: Array.from(
                        event.currentTarget.selectedOptions,
                        (option) => Number(option.value),
                      ),
                    })
                  }
                >
                  {(options.data?.users ?? data.team).map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="cluster">
              <Button type="submit">Enregistrer</Button>
              <Button
                type="button"
                variant="quiet"
                onClick={() => setEditForm(null)}
              >
                Annuler
              </Button>
            </div>
          </form>
        </Card>
      )}
      <section className="stack" aria-labelledby="project-tabs-title">
        <h2 id="project-tabs-title">Cycle des neuf onglets</h2>
        <div className="grid">
          {data.sections.map((section) => (
            <Card key={section.id}>
              <p className="eyebrow">{section.code}</p>
              <h3>{section.label}</h3>
              <StatusBadge status={section.state}>{section.state}</StatusBadge>
              {section.correction_reason && <p>{section.correction_reason}</p>}
              <p className="muted">{section.readiness_message}</p>
              <div className="cluster">
                <Button
                  variant="secondary"
                  onClick={() => openDraft(section.code)}
                >
                  Ouvrir le brouillon
                </Button>
                {section.capabilities.submit && (
                  <Button
                    onClick={() => void sectionTransition(section, "submit")}
                  >
                    Soumettre au {section.recipient_label}
                  </Button>
                )}
                {section.capabilities.verify && (
                  <Button
                    onClick={() => void sectionTransition(section, "verify")}
                  >
                    <CheckCircle2 size={17} /> Vérifier
                  </Button>
                )}
                {section.capabilities.correct && (
                  <Button
                    variant="secondary"
                    onClick={() => void sectionTransition(section, "correct")}
                  >
                    <RotateCcw size={17} /> Demander correction
                  </Button>
                )}
                {section.capabilities.validate && (
                  <Button
                    onClick={() => void sectionTransition(section, "validate")}
                  >
                    Valider électroniquement
                  </Button>
                )}
                {section.capabilities.close && (
                  <Button
                    onClick={() => void sectionTransition(section, "close")}
                  >
                    Clôturer l’onglet
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      </section>
      <div className="grid">
        {(
          [
            {
              resource: "action_plan",
              title: "Plan d’action",
              items: data.action_plan.map((item) => ({
                id: item.id,
                label: `${item.name} · ${item.progress} %`,
                values: item.values,
              })),
            },
            {
              resource: "results",
              title: "Résultats",
              items: data.results.map((item) => ({
                id: item.id,
                label: `${item.name} · cible ${item.target_value}`,
                values: item.values,
              })),
            },
            {
              resource: "deliverables",
              title: "Livrables",
              items: data.deliverables.map((item) => ({
                id: item.id,
                label: `${item.name}${item.at_risk ? " · à risque" : ""}`,
                values: item.values,
              })),
            },
            {
              resource: "finance",
              title: "Finances",
              items: data.budget.map((item) => ({
                id: item.id,
                label: `${item.code} — ${item.name} · disponible ${item.available_amount}`,
                values: item.values,
              })),
            },
            {
              resource: "compliance",
              title: "Conformité",
              items: data.compliance.map((item) => ({
                id: item.id,
                label: `${item.description} · ${item.state}`,
                values: item.values,
              })),
            },
            {
              resource: "risks",
              title: "Risques",
              items: data.risks.map((item) => ({
                id: item.id,
                label: `${item.title} · criticité ${item.severity}`,
                values: item.values,
              })),
            },
            {
              resource: "reports",
              title: "Rapports",
              items: data.reports.map((item) => ({
                id: item.id,
                label: `${item.title} · ${item.state}`,
                values: item.values,
              })),
            },
            {
              resource: "closure",
              title: "Clôture",
              items: data.closure.map((item) => ({
                id: item.id,
                label: item.assessment,
                values: item.values,
              })),
            },
          ] satisfies Array<{
            resource: ProjectResource;
            title: string;
            items: Array<{
              id: number;
              label: string;
              values: ProjectItemValues;
            }>;
          }>
        ).map(({ resource, title, items }) => {
          const section = data.sections.find((item) => item.code === resource);
          const editable = Boolean(
            data.capabilities.edit &&
            section &&
            !["validated", "closed"].includes(section.state),
          );
          const canAdd =
            editable && !(resource === "closure" && data.closure.length);
          const users = options.data?.users ?? data.team;
          const formUsers =
            resource === "action_plan"
              ? Array.from(
                  new Map(
                    [
                      ...data.team,
                      data.proposer,
                      ...(data.lead ? [data.lead] : []),
                    ].map((user) => [user.id, user]),
                  ).values(),
                )
              : users;
          return (
            <Card key={resource} id={`project-section-${resource}`}>
              <div className="cluster">
                <h2>{title}</h2>
                {section && (
                  <StatusBadge status={section.state}>
                    {section.state}
                  </StatusBadge>
                )}
              </div>
              {section && <p className="muted">{section.readiness_message}</p>}
              {!items.length ? (
                <p className="muted">Aucun élément.</p>
              ) : (
                <ul>
                  {items.map((item) => (
                    <li key={item.id}>
                      {item.label}
                      {editable && (
                        <ProjectItemForm
                          project={data}
                          resource={resource}
                          users={formUsers}
                          itemId={item.id}
                          initial={item.values}
                          onSaved={project.reload}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {canAdd && (
                <ProjectItemForm
                  project={data}
                  resource={resource}
                  users={formUsers}
                  onSaved={project.reload}
                  openLabel="Ouvrir le brouillon"
                />
              )}
            </Card>
          );
        })}
      </div>
    </>
  );
}
