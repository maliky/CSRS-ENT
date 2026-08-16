import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import type {
  ProcedureDetail,
  ProcedureOptions,
  ProcedureSummary,
} from "../../lib/api/types";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { ProcessesPage } from "./ProcessesPage";

const options: ProcedureOptions = {
  default_department_id: 4,
  process_types: [
    { value: "fund", label: "Bon de sortie de fonds" },
    { value: "purchase", label: "Demande d'achat" },
    { value: "absence", label: "Demande d'absence" },
    { value: "mission", label: "Ordre de mission" },
    { value: "payment_notice", label: "Notification de paiement" },
    { value: "visa", label: "Visa ou prolongation" },
    { value: "data", label: "Gestion des données" },
  ],
  departments: [{ id: 4, name: "Direction de la recherche" }],
  projects: [
    {
      id: 71,
      reference: "PRJ-0071",
      name: "Projet de terrain",
      budget_lines: [
        {
          id: 91,
          code: "FIELD",
          name: "Terrain",
          available_amount: 500000,
        },
      ],
    },
  ],
  people: [
    {
      id: 8,
      name: "Agent de recette",
      position: "Agent",
      login_alias: "agent",
      employee_id: 18,
      partner_id: 28,
    },
  ],
};

const requester = options.people[0];

function summary(overrides: Partial<ProcedureSummary> = {}): ProcedureSummary {
  return {
    id: 19,
    reference: "OM-00019",
    process_type: "mission",
    process_type_label: "Ordre de mission",
    state: "draft",
    state_label: "Brouillon",
    revision: 1,
    subject: "Mission Korhogo",
    description: "Supervision des sites",
    amount: 0,
    currency: "XOF",
    requester,
    origin_department: options.departments[0],
    project: null,
    correction_reason: "",
    available_actions: ["submit"],
    ...overrides,
  };
}

function renderPage(initialItems: ProcedureSummary[] = []) {
  let items = initialItems;
  let submitted: unknown = null;
  server.use(
    http.get("/api/v1/processes/options/", () => HttpResponse.json(options)),
    http.get("/api/v1/processes/", () => HttpResponse.json({ items })),
    http.post("/api/v1/processes/", async ({ request }) => {
      submitted = await request.json();
      const created: ProcedureDetail = {
        ...summary(),
        details: (submitted as { details: Record<string, unknown> }).details,
        events: [],
      };
      items = [created];
      return HttpResponse.json(created, { status: 201 });
    }),
  );
  render(
    <MemoryRouter initialEntries={["/procedures"]}>
      <Routes>
        <Route path="/procedures" element={<ProcessesPage />} />
      </Routes>
    </MemoryRouter>,
  );
  return { submitted: () => submitted };
}

test("présente les champs documentés selon la procédure choisie", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(
    await screen.findByRole("button", { name: "Nouveau dossier" }),
  );
  const procedure = screen.getByLabelText("Procédure");

  await user.selectOptions(procedure, "absence");
  expect(screen.getByLabelText("Agent")).toBeRequired();
  expect(screen.getByLabelText("Intérimaire")).toBeRequired();
  expect(screen.getByLabelText("Contact d’urgence")).toBeRequired();

  await user.selectOptions(procedure, "payment_notice");
  expect(screen.getByLabelText("Nature du paiement")).toBeRequired();
  expect(screen.getByLabelText("Preuve PDF ou image")).toBeRequired();

  await user.selectOptions(procedure, "visa");
  expect(screen.getByLabelText("Numéro de passeport")).toBeRequired();
  expect(screen.getByLabelText("Demande")).toBeRequired();

  await user.selectOptions(procedure, "data");
  expect(screen.getByLabelText("Plan de gestion")).toBeRequired();
  expect(screen.getByLabelText("Classification")).toBeRequired();
});

test("crée un brouillon de mission puis le rend visible", async () => {
  const user = userEvent.setup();
  const state = renderPage();

  expect(await screen.findByText("Aucun dossier")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Nouveau dossier" }));
  await user.type(screen.getByLabelText("Objet"), "Mission Korhogo");
  await user.type(
    screen.getByLabelText("Description"),
    "Supervision des sites",
  );
  await user.type(screen.getByLabelText("Destination"), "Korhogo");
  await user.type(screen.getByLabelText("Objet de la mission"), "Supervision");
  await user.type(screen.getByLabelText("Départ"), "2026-09-01");
  await user.type(screen.getByLabelText("Retour"), "2026-09-05");
  await user.click(screen.getByRole("button", { name: "Créer le brouillon" }));

  expect(await screen.findByText("Mission Korhogo")).toBeInTheDocument();
  expect(state.submitted()).toMatchObject({
    process_type: "mission",
    origin_department_id: 4,
    subject: "Mission Korhogo",
    details: {
      destination: "Korhogo",
      purpose: "Supervision",
      departure_date: "2026-09-01",
      return_date: "2026-09-05",
    },
  });
});
