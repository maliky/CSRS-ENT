import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

afterEach(() => vi.unstubAllGlobals());

test("affiche la connexion lorsque la session est anonyme", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: false }),
    }),
  );
  render(<App />);
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Connexion" }),
    ).toBeInTheDocument(),
  );
});

test("accueille l'identité validée par Odoo", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        authenticated: true,
        user: { id: 7, login: "agent", name: "Agent Test" },
      }),
    }),
  );
  render(<App />);
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Bonjour, Agent Test" }),
    ).toBeInTheDocument(),
  );
});
