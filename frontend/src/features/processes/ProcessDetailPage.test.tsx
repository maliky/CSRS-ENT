import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import type { ProcedureDetail } from "../../lib/api/types";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { ProcessDetailPage } from "./ProcessDetailPage";

const process: ProcedureDetail = {
  id: 19,
  reference: "DA-00019",
  process_type: "purchase",
  process_type_label: "Demande d'achat",
  state: "daf_review",
  state_label: "Visa DAF",
  revision: 3,
  subject: "Matériel de terrain",
  description: "Équipement nécessaire à la collecte",
  amount: 125000,
  currency: "XOF",
  requester: {
    id: 8,
    name: "Agent de recette",
    position: "Agent",
    login_alias: "agent",
  },
  origin_department: { id: 4, name: "Direction de la recherche" },
  project: null,
  correction_reason: "",
  available_actions: ["approve", "correct", "reject"],
  details: { quantity: 2, estimated_amount: 125000 },
  events: [],
};

function renderPage() {
  let attempts = 0;
  let currentProcess = process;
  server.use(
    http.get("/api/v1/processes/19/", () => HttpResponse.json(currentProcess)),
    http.post("/api/v1/processes/19/transition/", () => {
      attempts += 1;
      if (attempts === 1) {
        return HttpResponse.json(
          {
            error: {
              code: "stale_revision",
              message: "Le dossier a changé. Rechargez-le avant de continuer.",
              fields: {},
            },
          },
          { status: 409 },
        );
      }
      currentProcess = {
        ...process,
        state: "dg_review",
        state_label: "Validation DG",
        revision: 4,
        available_actions: [],
      };
      return HttpResponse.json(currentProcess);
    }),
  );
  render(
    <MemoryRouter initialEntries={["/procedures/19"]}>
      <Routes>
        <Route path="/procedures/:processId" element={<ProcessDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

test("efface une ancienne erreur après une transition réussie", async () => {
  const user = userEvent.setup();
  renderPage();

  const approve = await screen.findByRole("button", { name: /Approuver/ });
  await user.click(approve);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Le dossier a changé",
  );

  await user.click(approve);

  expect(await screen.findByText("Validation DG")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
