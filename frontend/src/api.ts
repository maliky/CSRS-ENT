export interface SessionUser {
  id: number;
  login: string;
  name: string;
}

export type SessionResponse =
  { authenticated: false } | { authenticated: true; user: SessionUser };

export function parseSessionPayload(value: unknown): SessionResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("Réponse de session invalide");
  }
  const payload = value as Record<string, unknown>;
  if (payload.authenticated === false) return { authenticated: false };
  if (
    payload.authenticated !== true ||
    typeof payload.user !== "object" ||
    payload.user === null
  ) {
    throw new Error("Réponse de session invalide");
  }
  const user = payload.user as Record<string, unknown>;
  if (
    typeof user.id !== "number" ||
    !Number.isInteger(user.id) ||
    typeof user.login !== "string" ||
    typeof user.name !== "string"
  ) {
    throw new Error("Identité de session invalide");
  }
  return {
    authenticated: true,
    user: { id: user.id, login: user.login, name: user.name },
  };
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

async function parseSession(response: Response): Promise<SessionResponse> {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return parseSessionPayload(await response.json());
}

export async function getSession(): Promise<SessionResponse> {
  return parseSession(
    await fetch("/api/v1/session/", { credentials: "same-origin" }),
  );
}

export async function login(
  loginValue: string,
  password: string,
): Promise<SessionResponse> {
  return parseSession(
    await fetch("/api/v1/session/login/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify({ login: loginValue, password }),
    }),
  );
}

export async function logout(): Promise<SessionResponse> {
  return parseSession(
    await fetch("/api/v1/session/logout/", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
    }),
  );
}
