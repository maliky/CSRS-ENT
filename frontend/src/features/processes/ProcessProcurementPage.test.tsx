import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import type { ProcedureDetail, ProcedureOptions } from "../../lib/api/types";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { ProcessDetailPage } from "./ProcessDetailPage";

const detail: ProcedureDetail = {
  id: 42,
  reference: "DA-0042",
  process_type: "purchase",
  process_type_label: "Demande d'achat",
  state: "procurement",
  state_label: "Traitement achat",
  revision: 4,
  subject: "Matériel de terrain",
  description: "Équipement de collecte",
  amount: 300000,
  currency: "XOF",
  requester: { id: 1, name: "Agent", position: "Agent", login_alias: "agent" },
  origin_department: { id: 2, name: "Recherche" },
  project: { id: 3, reference: "PRJ-3", name: "Projet terrain" },
  correction_reason: "",
  available_actions: ["order"],
  details: { budget_line_id: 99 },
  presentation: {
    kind: "purchase",
    budget_line: { id: 99, code: "TERRAIN", name: "Terrain" },
    quantity: 2,
    estimated_amount: 300000,
    negotiated_amount: 0,
    vendor: null,
    product: null,
    selected_quotation_id: null,
    quotations: [],
    purchase_order: null,
    evidence: [],
    documents: [],
  },
  events: [],
};

const options: ProcedureOptions = {
  default_department_id: 2,
  process_types: [],
  departments: [],
  projects: [],
  people: [],
  vendors: [{ id: 7, name: "Fournisseur" }],
  products: [{ id: 8, name: "Service de terrain" }],
};

test("présente la DA sans exposer les clés internes et ouvre la saisie achats", async () => {
  server.use(
    http.get("/api/v1/processes/42/", () => HttpResponse.json(detail)),
    http.get("/api/v1/processes/options/", () => HttpResponse.json(options)),
  );

  render(
    <MemoryRouter initialEntries={["/procedures/42"]}>
      <Routes>
        <Route path="/procedures/:processId" element={<ProcessDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole("heading", { name: "Matériel de terrain" }),
  ).toBeVisible();
  expect(screen.getByText("Ligne budgétaire")).toBeVisible();
  expect(screen.queryByText("budget_line_id")).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: /Ajouter une cotation/ }),
  ).toBeVisible();
  expect(screen.getByLabelText("Cotation retenue")).toBeVisible();
  expect(
    screen.getByRole("button", { name: /Créer le bon de commande/ }),
  ).toBeVisible();
});
