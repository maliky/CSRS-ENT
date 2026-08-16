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
  Person,
  ResearchProjectDetail,
  ResearchProjectSummary,
} from "../../lib/api/types";
import { useApi } from "../../lib/useApi";

type ProjectList = { items: ResearchProjectSummary[] };

export function ResearchProjectsPage() {
  const projects = useApi<ProjectList>("/api/v1/research-projects/");
  const options = useApi<{ users: Person[] }>(
    "/api/v1/research-projects/options/",
  );
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    objectives: "",
    institutional_commitments: "",
    date_start: "",
    date_end: "",
    donor_name: "",
    partner_names: "",
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
          partner_names: form.partner_names
            .split(",")
            .map((name) => name.trim())
            .filter(Boolean),
        }),
      });
      setForm({
        name: "",
        objectives: "",
        institutional_commitments: "",
        date_start: "",
        date_end: "",
        donor_name: "",
        partner_names: "",
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
              </div>
              <div className="form-field">
                <label htmlFor="project-donor">Bailleur</label>
                <input
                  id="project-donor"
                  value={form.donor_name}
                  onChange={(event) =>
                    setForm({ ...form, donor_name: event.target.value })
                  }
                />
              </div>
              <div className="form-field">
                <label htmlFor="project-partners">
                  Partenaires (séparés par des virgules)
                </label>
                <input
                  id="project-partners"
                  value={form.partner_names}
                  onChange={(event) =>
                    setForm({ ...form, partner_names: event.target.value })
                  }
                />
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
      {!projects.data.items.length ? (
        <EmptyState title="Aucun projet">
          Proposez le premier projet de recherche depuis ce registre.
        </EmptyState>
      ) : (
        <div className="grid">
          {projects.data.items.map((project) => (
            <Card key={project.id}>
              <div className="cluster">
                <FolderKanban aria-hidden="true" />
                <StatusBadge status={project.state}>
                  {project.state_label}
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
