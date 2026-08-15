import { type FormEvent, useEffect, useState } from "react";
import { AppRouter } from "./app/router";
import styles from "./app/login.module.css";
import { Button, Card } from "./components/ui";
import type { Session } from "./lib/api/types";

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; session: Session }
  | { status: "error"; message: string };

function csrfToken(): string {
  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith("csrftoken="));
  return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : "";
}

export function parseSession(value: unknown): Session {
  if (typeof value !== "object" || value === null) {
    throw new Error("Réponse de session invalide.");
  }
  const payload = value as Record<string, unknown>;
  const user = payload.user;
  if (
    typeof user !== "object" ||
    user === null ||
    typeof (user as Record<string, unknown>).id !== "number" ||
    typeof (user as Record<string, unknown>).name !== "string" ||
    typeof payload.capabilities !== "object" ||
    payload.capabilities === null
  ) {
    throw new Error("Réponse de session invalide.");
  }
  return payload as Session;
}

async function fetchSession(): Promise<AuthState> {
  const response = await fetch("/api/v1/session/", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (response.status === 401) return { status: "anonymous" };
  if (!response.ok)
    throw new Error("Le service de connexion est indisponible.");
  return {
    status: "authenticated",
    session: parseSession(await response.json()),
  };
}

export function App() {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void fetchSession()
      .then(setState)
      .catch(() =>
        setState({
          status: "error",
          message: "Le service de connexion est indisponible.",
        }),
      );
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/v1/session/login/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({
          login: String(data.get("login") ?? ""),
          password: String(data.get("password") ?? ""),
        }),
      });
      if (response.status === 401) {
        setError("Identifiant ou mot de passe incorrect.");
        return;
      }
      if (response.status === 429) {
        setError("Trop de tentatives. Réessayez dans quelques minutes.");
        return;
      }
      if (!response.ok) throw new Error("Connexion indisponible");
      setState({
        status: "authenticated",
        session: parseSession(await response.json()),
      });
    } catch {
      setError("La connexion n’a pas pu être établie.");
    } finally {
      setSubmitting(false);
    }
  }

  if (state.status === "loading")
    return (
      <main className={styles.statusPage}>
        <p>Chargement…</p>
      </main>
    );
  if (state.status === "error")
    return (
      <main className={styles.statusPage}>
        <div className="error-banner" role="alert">
          <h1>Connexion indisponible</h1>
          <p>{state.message}</p>
          <Button onClick={() => window.location.reload()}>Réessayer</Button>
        </div>
      </main>
    );
  if (state.status === "anonymous") {
    return (
      <main className={styles.loginPage}>
        <Card className={styles.loginCard}>
          <div className={styles.brandMark} aria-hidden="true">
            PE
          </div>
          <p className="eyebrow">Plateforme numérique de travail</p>
          <h1>Connexion à CSRS ENT</h1>
          <p className="muted">
            Utilisez votre adresse email ou votre identifiant court habituel.
          </p>
          <form
            className={styles.form}
            onSubmit={(event) => void submit(event)}
          >
            <div className="form-field">
              <label htmlFor="login">Email ou identifiant court</label>
              <input id="login" name="login" autoComplete="username" required />
            </div>
            <div className="form-field">
              <label htmlFor="password">Mot de passe</label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </div>
            {error && (
              <p className="error-banner" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Connexion…" : "Se connecter"}
            </Button>
          </form>
        </Card>
      </main>
    );
  }
  return <AppRouter />;
}
