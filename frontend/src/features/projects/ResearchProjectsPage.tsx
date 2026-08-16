import { FolderKanban, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorState,
  FrenchDateInput,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  Partner,
  Person,
  ResearchProjectDetail,
  ResearchProjectSummary,
} from "../../lib/api/types";
import { useApi } from "../../lib/useApi";

type ProjectList = { items: ResearchProjectSummary[] };
type ProjectOptions = { users: Person[]; partners: Partner[] };

export function ResearchProjectsPage() {
  const [view, setView] = useState<"mine" | "supervised" | "archived">("mine");
  const projects = useApi<ProjectList>(
    `/api/v1/research-projects/?status=${view === "archived" ? "archived" : "active"}`,
  );
  const options = useApi<ProjectOptions>("/api/v1/research-projects/options/");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    objectives: "",
    institutional_commitments: "",
    date_start: "",
    date_end: "",
    donor_id: "",
    partner_ids: [] as number[],
    team_user_ids: [] as number[],
  });
  const [mutationError, setMutationError] = useState("");

  async function createProject(event: FormEvent) {
    event.preventDefault();
    setMutationError("");
    try {
      await apiFetch<ResearchProjectDetail>("/api/v1/research-projects/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          date_start: form.date_start || null,
          date_end: form.date_end || null,
          donor_id: form.donor_id ? Number(form.donor_id) : null,
        }),
      });
      setForm({
        name: "",
        objectives: "",
        institutional_commitments: "",
        date_start: "",
        date_end: "",
        donor_id: "",
        partner_ids: [],
        team_user_ids: [],
      });
      setShowForm(false);
      await projects.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Création impossible.",
      );
    }
  }

  if (projects.loading) return <Skeleton label="Chargement des projets" />;
  if (projects.error || !projects.data)
    return (
      <ErrorState
        error={projects.error ?? new Error("Projets indisponibles")}
        retry={() => void projects.reload()}
      />
    );
  const visibleProjects = projects.data.items.filter((project) => {
    if (view === "archived") return project.archived;
    if (!project.access_scope) return view === "mine";
    if (view === "supervised")
      return (
        project.access_scope === "supervised" ||
        project.access_scope === "governance"
      );
    return project.access_scope === "owned" || project.access_scope === "team";
  });

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Recherche</p>
          <h1>Projets de recherche</h1>
          <p>
            Proposez un projet puis suivez son plan d’action, ses résultats,
            livrables, finances, risques, rapports et validations.
          </p>
        </div>
        <Button onClick={() => setShowForm((current) => !current)}>
          <Plus size={18} aria-hidden="true" /> Nouvelle proposition
        </Button>
      </header>
      <div className="cluster" role="group" aria-label="Vue des projets">
        <Button
          variant={view === "mine" ? "primary" : "secondary"}
          onClick={() => setView("mine")}
        >
          Mes projets
        </Button>
        <Button
          variant={view === "supervised" ? "primary" : "secondary"}
          onClick={() => setView("supervised")}
        >
          À superviser
        </Button>
        <Button
          variant={view === "archived" ? "primary" : "secondary"}
          onClick={() => setView("archived")}
        >
          Archivés
        </Button>
      </div>
      {showForm && (
        <Card>
          <form
            className="stack"
            onSubmit={(event) => void createProject(event)}
          >
            <h2>Proposer un projet</h2>
            {mutationError && (
              <p className="error-banner" role="alert">
                {mutationError}
              </p>
            )}
            <div className="form-grid">
              <div className="form-field wide">
                <label htmlFor="project-name">Intitulé</label>
                <input
                  id="project-name"
                  required
                  value={form.name}
                  onChange={(event) =>
                    setForm({ ...form, name: event.target.value })
                  }
                />
              </div>
              <div className="form-field wide">
                <label htmlFor="project-objectives">Objectifs</label>
                <textarea
                  id="project-objectives"
                  required
                  value={form.objectives}
                  onChange={(event) =>
                    setForm({ ...form, objectives: event.target.value })
                  }
                />
              </div>
              <div className="form-field wide">
                <label htmlFor="project-commitments">
                  Engagements institutionnels
                </label>
                <textarea
                  id="project-commitments"
                  value={form.institutional_commitments}
                  onChange={(event) =>
                    setForm({
                      ...form,
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
                <label htmlFor="project-donor">Bailleur</label>
                <select
                  id="project-donor"
                  value={form.donor_id}
                  onChange={(event) =>
                    setForm({ ...form, donor_id: event.target.value })
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
                <label htmlFor="project-partners">Partenaires</label>
                <select
                  id="project-partners"
                  multiple
                  value={form.partner_ids.map(String)}
                  onChange={(event) =>
                    setForm({
                      ...form,
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
              <div className="form-field wide">
                <label htmlFor="project-team">Équipe</label>
                <select
                  id="project-team"
                  multiple
                  value={form.team_user_ids.map(String)}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      team_user_ids: Array.from(
                        event.currentTarget.selectedOptions,
                        (option) => Number(option.value),
                      ),
                    })
                  }
                >
                  {(options.data?.users ?? []).map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="project-start">Début prévisionnel</label>
                <FrenchDateInput
                  id="project-start"
                  value={form.date_start}
                  onValueChange={(dateStart) =>
                    setForm({ ...form, date_start: dateStart })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="project-end">Fin prévisionnelle</label>
                <FrenchDateInput
                  id="project-end"
                  value={form.date_end}
                  onValueChange={(dateEnd) =>
                    setForm({ ...form, date_end: dateEnd })
                  }
                />
              </div>
            </div>
            <div className="cluster">
              <Button type="submit">Enregistrer la proposition</Button>
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
      {!visibleProjects.length ? (
        <EmptyState title="Aucun projet">
          Aucun projet ne correspond à cette vue.
        </EmptyState>
      ) : (
        <div className="grid">
          {visibleProjects.map((project) => (
            <Card key={project.id}>
              <div className="cluster">
                <FolderKanban aria-hidden="true" />
                <StatusBadge status={project.state}>
                  {project.archived ? "Archivé" : project.state_label}
                </StatusBadge>
              </div>
              <p className="eyebrow">{project.reference}</p>
              <h2>{project.name}</h2>
              <p className="muted">
                Proposé par {project.proposer.name}
                {project.lead ? ` · Chef : ${project.lead.name}` : ""}
              </p>
              <ButtonLink variant="secondary" to={`/projets/${project.id}`}>
                Ouvrir le projet
              </ButtonLink>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
