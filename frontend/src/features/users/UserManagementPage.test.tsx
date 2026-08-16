import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { UserManagementPage } from "./UserManagementPage";

const users = [
  [11, "Alpha"],
  [12, "Bravo"],
  [13, "Charlie"],
].map(([id, name]) => ({
  id,
  name,
  email: `${String(name).toLowerCase()}@example.invalid`,
  position: "Agent",
  login_alias: String(name).toLowerCase(),
  is_active: true,
  is_superuser: false,
  password_change_required: false,
  has_usable_password: true,
  primary_unit: null,
  state_token: `token-${id}`,
  batch_capabilities: { deactivate: true, delete: true },
}));

function renderPage() {
  const inactiveUserIds = new Set<number>();
  server.use(
    http.get("/api/v1/users/options/", () =>
      HttpResponse.json({
        today: "2026-08-16",
        units: [],
        users: [],
        agenda_directions: [],
      }),
    ),
    http.get("/api/v1/users/", ({ request }) => {
      const requestedState = new URL(request.url).searchParams.get("state");
      const items = users
        .filter((item) => {
          const inactive = inactiveUserIds.has(Number(item.id));
          if (requestedState === "inactive") return inactive;
          if (requestedState === "active") return !inactive;
          return true;
        })
        .map((item) => ({
          ...item,
          is_active: !inactiveUserIds.has(Number(item.id)),
          batch_capabilities: {
            deactivate: !inactiveUserIds.has(Number(item.id)),
            delete: inactiveUserIds.has(Number(item.id)),
          },
        }));
      return HttpResponse.json({
        items,
        total: items.length,
        page: 1,
        pages: 1,
        page_size: 20,
      });
    }),
    http.post("/api/v1/users/bulk-action/", async ({ request }) => {
      const body = (await request.json()) as {
        action: string;
        users: { id: number }[];
      };
      if (body.action === "deactivate") {
        for (const item of body.users) inactiveUserIds.add(item.id);
      }
      return HttpResponse.json({
        action: body.action,
        affected: body.users.length,
      });
    }),
  );
  render(
    <MemoryRouter initialEntries={["/administration/utilisateurs"]}>
      <Routes>
        <Route
          path="/administration/utilisateurs"
          element={<UserManagementPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

test("sélectionne toute la page depuis la case d’en-tête", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Alpha");

  await user.click(screen.getByRole("checkbox", { name: "Tout sélectionner" }));
  expect(screen.getByText(/3 sélectionné/)).toBeInTheDocument();

  expect(
    screen.getByRole("checkbox", { name: "Sélectionner Bravo" }),
  ).toBeChecked();
});

test("étend la sélection entre deux comptes avec Maj clic", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Alpha");

  await user.click(
    screen.getByRole("checkbox", { name: "Sélectionner Alpha" }),
  );
  expect(
    screen.getByRole("checkbox", { name: "Sélectionner Alpha" }),
  ).toBeChecked();
  fireEvent.click(
    screen.getByRole("checkbox", { name: "Sélectionner Charlie" }),
    { shiftKey: true },
  );

  expect(screen.getByText(/3 sélectionné/)).toBeInTheDocument();

  expect(
    screen.getByRole("checkbox", { name: "Sélectionner Bravo" }),
  ).toBeChecked();
});

test("affiche automatiquement les comptes inactifs après une désactivation", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Alpha");

  await user.click(
    screen.getByRole("checkbox", { name: "Sélectionner Alpha" }),
  );
  await user.click(screen.getByRole("button", { name: "Désactiver" }));
  await user.click(screen.getByRole("button", { name: "Confirmer" }));

  await waitFor(() =>
    expect(screen.getByLabelText("État")).toHaveValue("inactive"),
  );
  expect(await screen.findByText("Alpha")).toBeInTheDocument();
  expect(screen.getByText("Inactif")).toBeInTheDocument();
});
