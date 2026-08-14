import { FormEvent, useEffect, useState } from "react";
import { getSession, login, logout, SessionResponse } from "./api";

export function App() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void getSession()
      .then(setSession)
      .catch(() => setSession({ authenticated: false }));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      setSession(
        await login(
          String(data.get("login") ?? ""),
          String(data.get("password") ?? ""),
        ),
      );
    } catch {
      setError("Identifiant ou mot de passe incorrect.");
    }
  }

  if (session === null)
    return (
      <main className="shell">
        <p>Chargement…</p>
      </main>
    );
  if (!session.authenticated) {
    return (
      <main className="shell login-card">
        <p className="eyebrow">ENT du CSRS</p>
        <h1>Connexion</h1>
        <form onSubmit={(event) => void submit(event)}>
          <label htmlFor="login">Email ou identifiant court</label>
          <input id="login" name="login" autoComplete="username" required />
          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button type="submit">Se connecter</button>
        </form>
      </main>
    );
  }
  return (
    <main className="shell">
      <p className="eyebrow">Espace de travail</p>
      <h1>Bonjour, {session.user.name}</h1>
      <p>
        Votre compte Odoo est connecté. Les tâches et tableaux de bord seront
        ajoutés progressivement ici.
      </p>
      <button type="button" onClick={() => void logout().then(setSession)}>
        Se déconnecter
      </button>
    </main>
  );
}
