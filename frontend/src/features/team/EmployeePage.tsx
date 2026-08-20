import { useState, type FormEvent } from "react";
import { useLocation, useParams } from "../../lib/router";
import { apiFetch } from "../../lib/api/client";
import type { TeamEmployee, TeamEmployeeProfile } from "../../lib/api/types";
import { useApi } from "../../lib/useApi";
import {
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "../../components/ui";
import { PeriodNavigation } from "../tasks/PeriodNavigation";
import { TaskCard } from "../tasks/TaskCard";
import styles from "./team.module.css";

type EncodedFile = {
  name: string;
  mimetype: string;
  content_base64: string;
};

function encodedFile(file: File): Promise<EncodedFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Lecture du fichier impossible."));
    reader.onload = () => {
      const value = String(reader.result ?? "");
      const separator = value.indexOf(",");
      if (separator < 0) {
        reject(new Error("Lecture du fichier impossible."));
        return;
      }
      resolve({
        name: file.name,
        mimetype: file.type,
        content_base64: value.slice(separator + 1),
      });
    };
    reader.readAsDataURL(file);
  });
}

export function EmployeePage() {
  const { employeeId } = useParams();
  const location = useLocation();
  const { data, error, loading, reload } = useApi<TeamEmployee>(
    `/api/v1/team/${employeeId}/${location.search}`,
  );
  if (loading) return <Skeleton label="Chargement du collaborateur" />;
  if (error || !data)
    return (
      <ErrorState
        error={error ?? new Error("Collaborateur indisponible")}
        retry={reload}
      />
    );
  return (
    <>
      <header className="page-heading">
        <div className={styles.employeeHeading}>
          {data.profile.has_avatar && (
            <img
              className={styles.profileAvatar}
              src={`/api/v1/team/${data.employee.id}/avatar/?v=${data.profile.state_token}`}
              alt={`Avatar de ${data.employee.name}`}
            />
          )}
          <div>
            <p className="eyebrow">Progression et charge</p>
            <h1>{data.employee.name}</h1>
            <p>{data.employee.position || "Collaborateur"}</p>
          </div>
        </div>
        <ButtonLink to={`/equipe${location.search}`} variant="quiet">
          Retour à l'équipe
        </ButtonLink>
      </header>
      <EmployeeProfileCard
        key={data.profile.state_token}
        employeeId={data.employee.id}
        profile={data.profile}
        onSaved={reload}
      />
      <PeriodNavigation period={data.period} />
      {data.tasks.length ? (
        <div className="grid">
          {data.tasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
      ) : (
        <EmptyState title="Aucune tâche sur cette période">
          Changez de période pour consulter d'autres engagements.
        </EmptyState>
      )}
    </>
  );
}

function EmployeeProfileCard({
  employeeId,
  profile,
  onSaved,
}: {
  employeeId: number;
  profile: TeamEmployeeProfile;
  onSaved: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [terms, setTerms] = useState(profile.terms_of_reference);
  const [avatar, setAvatar] = useState<File | null>(null);
  const [document, setDocument] = useState<File | null>(null);
  const [removeAvatar, setRemoveAvatar] = useState(false);
  const [removeDocument, setRemoveDocument] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      for (const file of [avatar, document]) {
        if (file && file.size > 5 * 1024 * 1024)
          throw new Error("Chaque fichier doit peser au maximum 5 Mo.");
      }
      const payload: Record<string, unknown> = {
        state_token: profile.state_token,
        terms_of_reference: terms,
        remove_avatar: removeAvatar,
        remove_document: removeDocument,
      };
      if (avatar) payload.avatar = await encodedFile(avatar);
      if (document) payload.document = await encodedFile(document);
      await apiFetch<TeamEmployeeProfile>(`/api/v1/team/${employeeId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setEditing(false);
      await onSaved();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Enregistrement impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className={styles.employeeProfile}>
      <div className={styles.profileTitle}>
        <div>
          <p className="eyebrow">Profil professionnel</p>
          <h2>Cahier des charges</h2>
        </div>
        {profile.can_edit && !editing && (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            Modifier mon profil
          </Button>
        )}
      </div>
      {editing ? (
        <form className="stack" onSubmit={(event) => void submit(event)}>
          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}
          <label htmlFor="terms-of-reference">
            Missions et responsabilités
          </label>
          <textarea
            id="terms-of-reference"
            rows={10}
            maxLength={20_000}
            value={terms}
            onChange={(event) => setTerms(event.target.value)}
          />
          <label htmlFor="profile-avatar">
            Avatar (JPEG ou PNG, 5 Mo maximum)
          </label>
          <input
            id="profile-avatar"
            type="file"
            accept="image/jpeg,image/png"
            onChange={(event) => setAvatar(event.target.files?.[0] ?? null)}
          />
          {profile.has_avatar && (
            <label>
              <input
                type="checkbox"
                checked={removeAvatar}
                onChange={(event) => setRemoveAvatar(event.target.checked)}
              />{" "}
              Supprimer l'avatar actuel
            </label>
          )}
          <label htmlFor="tor-document">
            Document TOR (PDF, DOC ou DOCX, 5 Mo maximum)
          </label>
          <input
            id="tor-document"
            type="file"
            accept="application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => setDocument(event.target.files?.[0] ?? null)}
          />
          {profile.document && (
            <label>
              <input
                type="checkbox"
                checked={removeDocument}
                onChange={(event) => setRemoveDocument(event.target.checked)}
              />{" "}
              Supprimer le document actuel
            </label>
          )}
          <div className="cluster">
            <Button type="submit" disabled={saving}>
              {saving ? "Enregistrement…" : "Enregistrer le profil"}
            </Button>
            <Button
              type="button"
              variant="quiet"
              onClick={() => setEditing(false)}
            >
              Annuler
            </Button>
          </div>
        </form>
      ) : (
        <>
          <p className={styles.termsText}>
            {profile.terms_of_reference ||
              "Aucun cahier des charges renseigné."}
          </p>
          {profile.document && (
            <a href={`/api/v1/team/${employeeId}/tor-document/`}>
              Télécharger {profile.document.name}
            </a>
          )}
        </>
      )}
    </Card>
  );
}
