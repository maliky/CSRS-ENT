import { KeyRound, LogOut } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Card } from "../../components/ui";
import { ApiError, apiFetch } from "../../lib/api/client";
import styles from "./users.module.css";

export function PasswordChangePage({
  onComplete,
  onLogout,
  forced = true,
  professionalEmail = "",
}: {
  onComplete: () => Promise<unknown> | unknown;
  onLogout: () => Promise<unknown> | unknown;
  forced?: boolean;
  professionalEmail?: string;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch<void>("/api/v1/session/password/", {
        method: "POST",
        body: JSON.stringify({
          current_password: form.get("current_password"),
          new_password: form.get("new_password"),
          new_password_confirmation: form.get("new_password_confirmation"),
        }),
      });
      await onComplete();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Le mot de passe n’a pas pu être remplacé.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={styles.passwordPage}>
      <Card className={styles.passwordCard}>
        <p className="eyebrow">Sécurité du compte</p>
        <h1>
          {forced ? "Choisir un nouveau mot de passe" : "Compte et sécurité"}
        </h1>
        <p>
          {forced
            ? "Le mot de passe transmis par l’administrateur est temporaire. Remplacez-le avant d’accéder à l’application."
            : "Modifiez votre mot de passe local. Vous devrez ensuite vous reconnecter."}
        </p>
        {professionalEmail && (
          <p>
            <strong>Adresse professionnelle :</strong> {professionalEmail}
          </p>
        )}
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        <form className="stack" onSubmit={(event) => void submit(event)}>
          <div className="form-field">
            <label htmlFor="temporary-password">
              {forced ? "Mot de passe temporaire" : "Mot de passe actuel"}
            </label>
            <input
              id="temporary-password"
              name="current_password"
              type="password"
              autoComplete="current-password"
              required
            />
          </div>
          <div className="form-field">
            <label htmlFor="new-password">Nouveau mot de passe</label>
            <input
              id="new-password"
              name="new_password"
              type="password"
              autoComplete="new-password"
              required
            />
          </div>
          <div className="form-field">
            <label htmlFor="new-password-confirmation">
              Confirmer le nouveau mot de passe
            </label>
            <input
              id="new-password-confirmation"
              name="new_password_confirmation"
              type="password"
              autoComplete="new-password"
              required
            />
          </div>
          <div className="cluster">
            <Button disabled={saving}>
              <KeyRound size={18} aria-hidden="true" />
              {saving ? "Enregistrement…" : "Enregistrer"}
            </Button>
            <Button
              type="button"
              variant="quiet"
              disabled={saving}
              onClick={() => void onLogout()}
            >
              <LogOut size={18} aria-hidden="true" /> Déconnexion
            </Button>
          </div>
        </form>
      </Card>
    </section>
  );
}
