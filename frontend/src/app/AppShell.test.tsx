import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "../lib/router";
import { AppShell } from "./AppShell";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { sessionFixture } from "../mocks/fixtures";

test("réduit la barre latérale et mémorise le choix", async () => {
  window.localStorage.clear();
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<h1>Contenu de test</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Contenu de test")).toBeInTheDocument();
  const team = screen.getByRole("link", { name: "Mon équipe" });
  const proposals = screen.getByRole("link", { name: "Propositions" });
  expect(
    screen.queryByRole("link", { name: "Interface classique" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Processus" }),
  ).not.toBeInTheDocument();
  expect(
    team.compareDocumentPosition(proposals) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Réduire le menu" }));
  expect(window.localStorage.getItem("csrs_ent.sidebar.collapsed")).toBe(
    "true",
  );
  expect(
    screen.getByRole("button", { name: "Déployer le menu" }),
  ).toBeInTheDocument();
});

test("regroupe les parcours liés dans des sections repliables", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<h1>Navigation groupée</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  await screen.findByText("Navigation groupée");
  const workGroup = screen.getByText("Travail");
  const team = screen.getByRole("link", { name: "Mon équipe" });
  expect(team).toBeVisible();

  await user.click(workGroup);

  expect(team).not.toBeVisible();
  expect(screen.getByText("Pilotage")).toBeInTheDocument();
});

test("ouvre et ferme le tiroir mobile avec des contrôles accessibles", async () => {
  window.localStorage.clear();
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<h1>Contenu mobile</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  await screen.findByText("Contenu mobile");
  const open = screen.getByRole("button", {
    name: "Ouvrir le menu",
    hidden: true,
  });
  fireEvent.click(open);
  expect(open).toHaveAttribute("aria-expanded", "true");
  const close = screen.getByRole("button", {
    name: "Fermer le menu",
    hidden: true,
  });
  fireEvent.click(close);
  expect(open).toHaveAttribute("aria-expanded", "false");
});

test("bloque la navigation tant que le mot de passe temporaire subsiste", async () => {
  server.use(
    http.get("/api/v1/session/", () =>
      HttpResponse.json({
        ...sessionFixture,
        capabilities: {
          ...sessionFixture.capabilities,
          password_change_required: true,
        },
      }),
    ),
  );
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<h1>Contenu protégé</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole("heading", {
      name: "Choisir un nouveau mot de passe",
    }),
  ).toBeInTheDocument();
  expect(screen.queryByText("Contenu protégé")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Mon équipe" }),
  ).not.toBeInTheDocument();
});

test("affiche les outils d'administration uniquement avec les droits Odoo", async () => {
  server.use(
    http.get("/api/v1/session/", () =>
      HttpResponse.json({
        ...sessionFixture,
        capabilities: {
          ...sessionFixture.capabilities,
          delete_tasks: true,
          manage_users: true,
          manage_organization: true,
          manage_partners: true,
        },
      }),
    ),
  );
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<h1>Administration</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole("heading", { name: "Administration" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Gérer les tâches" }),
  ).toHaveAttribute("href", "/administration/taches");
  expect(screen.getByRole("link", { name: "Utilisateurs" })).toHaveAttribute(
    "href",
    "/administration/utilisateurs",
  );
  expect(screen.getByRole("link", { name: "Organigramme" })).toHaveAttribute(
    "href",
    "/administration/organigramme",
  );
  expect(screen.getByRole("link", { name: "Organisations" })).toHaveAttribute(
    "href",
    "/administration/organisations",
  );
});

test("permet à l'administrateur d'activer une vue de rôle auditée", async () => {
  let selectedRole: unknown = null;
  const roles = [
    { code: "hr", label: "Ressources humaines" },
    { code: "finance", label: "Finances et comptabilité" },
  ];
  server.use(
    http.get("/api/v1/session/", () =>
      HttpResponse.json({
        ...sessionFixture,
        role_switcher: {
          can_switch: true,
          active_code: null,
          active_label: null,
          roles,
        },
      }),
    ),
    http.post("/api/v1/session/role/", async ({ request }) => {
      selectedRole = ((await request.json()) as { role_code: unknown })
        .role_code;
      return HttpResponse.json({
        ...sessionFixture,
        capabilities: {
          ...sessionFixture.capabilities,
          admin: false,
          manage_availability: true,
        },
        role_switcher: {
          can_switch: true,
          active_code: "hr",
          active_label: "Ressources humaines",
          roles,
        },
      });
    }),
  );
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<h1>Tableau de bord</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  await user.selectOptions(
    await screen.findByRole("combobox", { name: "Rôle actif" }),
    "hr",
  );

  expect(selectedRole).toBe("hr");
  expect(
    await screen.findByText(/Vue active : Ressources humaines/),
  ).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Rôle actif" })).toHaveValue(
    "hr",
  );
});

test("signale le miroir historique et renvoie la saisie vers CSRS Report", async () => {
  server.use(
    http.get("/api/v1/session/", () =>
      HttpResponse.json({
        ...sessionFixture,
        reporting: {
          ...sessionFixture.reporting,
          mode: "legacy_mirror",
          write_enabled: false,
          last_success_at: "2026-08-25 02:18:00",
        },
      }),
    ),
  );
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<h1>Consultation</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Consultation synchronisée.")).toBeVisible();
  expect(screen.getByRole("link", { name: "CSRS Report" })).toHaveAttribute(
    "href",
    "https://179.237.107.40/app/",
  );
});
