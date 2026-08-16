import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { ResearchProjectsPage } from "./ResearchProjectsPage";

test("sépare les projets personnels, supervisés et archivés", async () => {
  const user = userEvent.setup();
  const summary = (name: string, access_scope: string, archived = false) => ({
    id: name.length,
    reference: `TEST-${name.length}`,
    name,
    state: "active",
    state_label: "Actif",
    revision: 1,
    proposer: { id: 1, name: "Agent", position: "", login_alias: "agent" },
    lead: null,
    date_start: null,
    date_end: null,
    access_scope,
    archived,
    capabilities: {
      edit: !archived,
      supervise: access_scope === "supervised",
      archive: access_scope === "supervised" && !archived,
      approve: false,
      reject: false,
      close: false,
    },
  });
  server.use(
    http.get("/api/v1/research-projects/", ({ request }) => {
      const status = new URL(request.url).searchParams.get("status");
      return HttpResponse.json({
        items:
          status === "archived"
            ? [summary("Projet archivé", "supervised", true)]
            : [
                summary("Mon projet", "owned"),
                summary("Projet supervisé", "supervised"),
              ],
      });
    }),
    http.get("/api/v1/research-projects/options/", () =>
      HttpResponse.json({ users: [], partners: [] }),
    ),
  );
  render(
    <MemoryRouter initialEntries={["/projets"]}>
      <Routes>
        <Route path="/projets" element={<ResearchProjectsPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Mon projet")).toBeInTheDocument();
  expect(screen.queryByText("Projet supervisé")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "À superviser" }));
  expect(await screen.findByText("Projet supervisé")).toBeInTheDocument();
  expect(screen.queryByText("Mon projet")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Archivés" }));
  await waitFor(() =>
    expect(screen.getByText("Projet archivé")).toBeInTheDocument(),
  );
});

test("enregistre une proposition puis l’affiche dans la liste", async () => {
  const user = userEvent.setup();
  let project: Record<string, unknown> | null = null;
  let submitted: Record<string, unknown> | null = null;
  server.use(
    http.get("/api/v1/research-projects/", () =>
      HttpResponse.json({ items: project ? [project] : [] }),
    ),
    http.get("/api/v1/research-projects/options/", () =>
      HttpResponse.json({
        users: [],
        partners: [
          { id: 31, name: "Fondation santé" },
          { id: 32, name: "Université partenaire" },
        ],
      }),
    ),
    http.post("/api/v1/research-projects/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      submitted = body;
      project = {
        id: 71,
        reference: "CSRS-PRJ-2026-0071",
        name: body.name,
        state: "proposal",
        state_label: "Proposition",
        proposer: {
          id: 7,
          name: "Agent",
          position: "Agent",
          login_alias: "agent",
        },
        lead: null,
      };
      return HttpResponse.json(project, { status: 201 });
    }),
  );
  render(
    <MemoryRouter initialEntries={["/projets"]}>
      <Routes>
        <Route path="/projets" element={<ResearchProjectsPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await user.click(
    await screen.findByRole("button", { name: "Nouvelle proposition" }),
  );
  await user.type(screen.getByLabelText("Intitulé"), "Projet sentinelle");
  await user.type(
    screen.getByLabelText("Objectifs"),
    "Tester le parcours complet",
  );
  await user.selectOptions(screen.getByLabelText("Bailleur"), "31");
  await user.selectOptions(screen.getByLabelText("Partenaires"), "32");
  await user.click(
    screen.getByRole("button", { name: "Enregistrer la proposition" }),
  );

  expect(await screen.findByText("Projet sentinelle")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Ouvrir le projet" }),
  ).toHaveAttribute("href", "/projets/71");
  expect(submitted).toMatchObject({ donor_id: 31, partner_ids: [32] });
});
