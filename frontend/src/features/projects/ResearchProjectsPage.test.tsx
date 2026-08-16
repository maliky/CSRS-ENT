import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { ResearchProjectsPage } from "./ResearchProjectsPage";

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
