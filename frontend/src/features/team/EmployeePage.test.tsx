import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { dashboardFixture } from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import { EmployeePage } from "./EmployeePage";

test("affiche le cahier des charges et permet à l'employé de le modifier", async () => {
  const user = userEvent.setup();
  let submitted: Record<string, unknown> | null = null;
  const employee = {
    id: 17,
    name: "Awa Finances",
    position: "Responsable des finances",
    login_alias: "finances",
  };
  server.use(
    http.get("/api/v1/team/17/", () =>
      HttpResponse.json({
        period: dashboardFixture.period,
        employee,
        profile: {
          terms_of_reference: "Préparer les états financiers.",
          has_avatar: false,
          document: {
            name: "cahier-des-charges.pdf",
            mimetype: "application/pdf",
          },
          can_edit: true,
          state_token: "a".repeat(64),
        },
        tasks: [],
      }),
    ),
    http.patch("/api/v1/team/17/", async ({ request }) => {
      submitted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ state_token: "b".repeat(64) });
    }),
  );
  render(
    <MemoryRouter initialEntries={["/equipe/17"]}>
      <Routes>
        <Route path="/equipe/:employeeId" element={<EmployeePage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByText("Préparer les états financiers."),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Télécharger cahier-des-charges.pdf" }),
  ).toHaveAttribute("href", "/api/v1/team/17/tor-document/");

  await user.click(screen.getByRole("button", { name: "Modifier mon profil" }));
  await user.clear(screen.getByLabelText("Missions et responsabilités"));
  await user.type(
    screen.getByLabelText("Missions et responsabilités"),
    "Préparer, contrôler et archiver les états financiers.",
  );
  await user.click(
    screen.getByRole("button", { name: "Enregistrer le profil" }),
  );

  await waitFor(() =>
    expect(submitted).toMatchObject({
      state_token: "a".repeat(64),
      terms_of_reference:
        "Préparer, contrôler et archiver les états financiers.",
    }),
  );
});
