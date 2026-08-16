import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { vi } from "vitest";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import type { ResearchProjectDetail } from "../../lib/api/types";
import { server } from "../../mocks/server";
import { ResearchProjectDetailPage } from "./ResearchProjectDetailPage";

const person = {
  id: 7,
  name: "Aïssata Koné",
  position: "Chercheuse",
  login_alias: "akone",
};

function projectFixture(): ResearchProjectDetail {
  return {
    id: 71,
    reference: "CSRS-PRJ-2026-0071",
    name: "Projet paludisme",
    state: "proposal",
    state_label: "Proposition",
    revision: 4,
    proposer: person,
    lead: null,
    date_start: "2026-09-01",
    date_end: "2027-08-31",
    access_scope: "owned",
    archived: false,
    capabilities: {
      edit: true,
      supervise: false,
      archive: false,
      approve: false,
      reject: false,
      close: false,
    },
    objectives: "Mesurer l’incidence.",
    institutional_commitments: "Laboratoire et terrain",
    team: [person],
    donor: null,
    partners: [],
    sections: [
      ["project", "Projet"],
      ["action_plan", "Plan d’action"],
      ["results", "Résultats"],
      ["deliverables", "Livrables"],
      ["finance", "Finances"],
      ["compliance", "Conformité"],
      ["risks", "Risques"],
      ["reports", "Rapports"],
      ["closure", "Clôture"],
    ].map(([code, label], index) => ({
      id: index + 1,
      code,
      label,
      sequence: index + 1,
      required: ["project", "action_plan", "finance", "closure"].includes(code),
      unlocked: true,
      state: "draft",
      revision: 1,
      correction_reason: "",
      ready: true,
      readiness_message: "Brouillon prêt à être soumis.",
      recipient_label: "contrôle du projet",
      capabilities: {
        submit: true,
        verify: false,
        correct: false,
        validate: false,
        close: false,
      },
    })),
    recap_unlocked: true,
    action_plan: [],
    budget: [],
    risks: [],
    results: [],
    deliverables: [],
    compliance: [],
    reports: [],
    closure: [],
  };
}

test("affiche le parcours numéroté avec dix écrans", async () => {
  server.use(
    http.get("/api/v1/research-projects/71/", () =>
      HttpResponse.json(projectFixture()),
    ),
    http.get("/api/v1/research-projects/options/", () =>
      HttpResponse.json({ users: [person] }),
    ),
  );
  render(
    <MemoryRouter initialEntries={["/projets/71"]}>
      <Routes>
        <Route
          path="/projets/:projectId"
          element={<ResearchProjectDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

  const journey = await screen.findByRole("navigation", {
    name: "Parcours du projet",
  });
  expect(within(journey).getAllByRole("button")).toHaveLength(10);
  expect(
    within(journey).getByRole("button", { name: /1\. Projet/ }),
  ).toHaveAttribute("aria-current", "step");
});

test("explique qu'une finance vide ne peut pas être soumise", async () => {
  const project = projectFixture();
  project.sections = project.sections.map((section) =>
    section.code === "finance"
      ? {
          ...section,
          ready: false,
          readiness_message:
            "Ajoutez au moins une ligne budgétaire avant de soumettre.",
          recipient_label: "contrôle financier",
          capabilities: { ...section.capabilities, submit: false },
        }
      : section,
  );
  server.use(
    http.get("/api/v1/research-projects/71/", () => HttpResponse.json(project)),
    http.get("/api/v1/research-projects/options/", () =>
      HttpResponse.json({ users: [person], partners: [] }),
    ),
  );
  render(
    <MemoryRouter initialEntries={["/projets/71?etape=finance"]}>
      <Routes>
        <Route
          path="/projets/:projectId"
          element={<ResearchProjectDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

  const finance = (
    await screen.findByRole("heading", { name: "Finances" })
  ).closest("section");
  expect(finance).not.toBeNull();
  expect(
    within(finance as HTMLElement).getByText(
      "Ajoutez au moins une ligne budgétaire avant de soumettre.",
    ),
  ).toBeInTheDocument();
  expect(
    within(finance as HTMLElement).queryByRole("button", { name: /Soumettre/ }),
  ).not.toBeInTheDocument();
});

test("ajoute un résultat avec la révision courante du projet", async () => {
  const user = userEvent.setup();
  let project = projectFixture();
  let receivedRevision = 0;
  server.use(
    http.get("/api/v1/research-projects/71/", () => HttpResponse.json(project)),
    http.get("/api/v1/research-projects/options/", () =>
      HttpResponse.json({ users: [person] }),
    ),
    http.post(
      "/api/v1/research-projects/71/items/results/",
      async ({ request }) => {
        const body = (await request.json()) as {
          revision: number;
          values: Record<string, string>;
        };
        receivedRevision = body.revision;
        project = {
          ...project,
          revision: 5,
          results: [
            {
              id: 91,
              name: body.values.name,
              indicator: body.values.indicator,
              target_value: body.values.target_value,
              achieved_value: body.values.achieved_value,
              values: body.values,
            },
          ],
        };
        return HttpResponse.json(project, { status: 201 });
      },
    ),
  );

  render(
    <MemoryRouter initialEntries={["/projets/71"]}>
      <Routes>
        <Route
          path="/projets/:projectId"
          element={<ResearchProjectDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole("heading", { name: "Projet paludisme" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /3\. Résultats/ }));
  const results = screen
    .getByRole("heading", { name: "Résultats" })
    .closest("section");
  expect(results).not.toBeNull();
  await user.click(
    within(results as HTMLElement).getByRole("button", {
      name: "Ouvrir le brouillon",
    }),
  );
  await user.type(
    within(results as HTMLElement).getByLabelText("Résultat"),
    "Deux publications",
  );
  await user.type(
    within(results as HTMLElement).getByLabelText("Indicateur"),
    "Publications",
  );
  await user.type(within(results as HTMLElement).getByLabelText("Cible"), "2");
  await user.click(
    within(results as HTMLElement).getByRole("button", { name: "Enregistrer" }),
  );

  await waitFor(() => expect(receivedRevision).toBe(4));
  expect(
    await screen.findByText("Deux publications · cible 2"),
  ).toBeInTheDocument();
});

test("archive un projet supervisé avec un motif explicite", async () => {
  const user = userEvent.setup();
  let project = projectFixture();
  project.capabilities = {
    ...project.capabilities,
    edit: true,
    supervise: true,
    archive: true,
  };
  let payload: Record<string, unknown> | null = null;
  vi.spyOn(window, "prompt").mockReturnValue("Projet remplacé.");
  vi.spyOn(window, "confirm").mockReturnValue(true);
  server.use(
    http.get("/api/v1/research-projects/71/", () => HttpResponse.json(project)),
    http.get("/api/v1/research-projects/options/", () =>
      HttpResponse.json({ users: [person], partners: [] }),
    ),
    http.post(
      "/api/v1/research-projects/71/transition/",
      async ({ request }) => {
        payload = (await request.json()) as Record<string, unknown>;
        project = {
          ...project,
          archived: true,
          capabilities: {
            ...project.capabilities,
            edit: false,
            archive: false,
          },
        };
        return HttpResponse.json(project);
      },
    ),
  );
  render(
    <MemoryRouter initialEntries={["/projets/71"]}>
      <Routes>
        <Route
          path="/projets/:projectId"
          element={<ResearchProjectDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: "Archiver" }));

  await waitFor(() =>
    expect(payload).toMatchObject({
      action: "archive",
      revision: 4,
      reason: "Projet remplacé.",
    }),
  );
  expect(await screen.findByText("Archivé")).toBeInTheDocument();
});
