import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { App, parseSession } from "./App";

afterEach(() => vi.unstubAllGlobals());

test("refuse une session non typée", () => {
  expect(() => parseSession({ user: { id: "7", name: "Agent" } })).toThrow(
    "Réponse de session invalide",
  );
});

test("affiche l’unique écran de connexion pour une session anonyme", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 401, ok: false }));

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Connexion à CSRS ENT" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Se connecter" }),
  ).toBeInTheDocument();
});

test("affiche un refus explicite sans conserver le mot de passe", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ status: 401, ok: false })
    .mockResolvedValueOnce({ status: 401, ok: false });
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "Connexion à CSRS ENT" });

  await user.type(screen.getByLabelText("Email ou identifiant court"), "agent");
  await user.type(screen.getByLabelText("Mot de passe"), "incorrect");
  await user.click(screen.getByRole("button", { name: "Se connecter" }));

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Identifiant ou mot de passe incorrect",
    ),
  );
  expect(fetchMock).toHaveBeenLastCalledWith(
    "/api/v1/session/login/",
    expect.objectContaining({ method: "POST" }),
  );
});

test("ouvre l’espace CSRS ENT après validation de la session", async () => {
  render(<App />);

  expect((await screen.findAllByText("CSRS ENT")).length).toBeGreaterThan(0);
  expect(
    await screen.findByText("Finaliser les priorités de la quinzaine"),
  ).toBeInTheDocument();
});
