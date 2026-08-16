import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import type {
  ManagedUserDetail,
  UserManagementOptions,
} from "../../lib/api/types";
import { MemoryRouter, Route, Routes } from "../../lib/router";
import { UserFormPage } from "./UserFormPage";

const options: UserManagementOptions = {
  today: "2026-08-16",
  units: [],
  users: [],
  agenda_directions: [],
};

const inactiveUser: ManagedUserDetail = {
  id: 44,
  name: "Compte inactif",
  email: "inactive@example.invalid",
  position: "Agent",
  login_alias: "inactive-user",
  is_active: false,
  is_superuser: false,
  password_change_required: false,
  has_usable_password: true,
  primary_unit: null,
  state_token: "inactive-token",
  batch_capabilities: { deactivate: false, delete: true },
  first_name: "Compte",
  last_name: "Inactif",
  phone: "",
  agenda_direction: "",
  include_in_direction_agendas: true,
  unit_ids: [],
  primary_unit_id: null,
  primary_supervisor: null,
  capabilities: {
    deactivate: false,
    reactivate: true,
    reset_password: false,
    send_activation: false,
    edit: true,
  },
};

test("réactive un compte archivé et conserve la confirmation visible", async () => {
  const user = userEvent.setup();
  server.use(
    http.get("/api/v1/users/options/", () => HttpResponse.json(options)),
    http.get("/api/v1/users/44/", () => HttpResponse.json(inactiveUser)),
    http.post("/api/v1/users/44/reactivate/", () =>
      HttpResponse.json({
        ...inactiveUser,
        is_active: true,
        state_token: "active-token",
        batch_capabilities: { deactivate: true, delete: false },
        capabilities: {
          ...inactiveUser.capabilities,
          deactivate: true,
          reactivate: false,
          reset_password: true,
        },
      }),
    ),
  );
  render(
    <MemoryRouter initialEntries={["/administration/utilisateurs/44"]}>
      <Routes>
        <Route
          path="/administration/utilisateurs/:userId"
          element={<UserFormPage mode="edit" />}
        />
      </Routes>
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: "Réactiver" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Compte réactivé.",
  );
  expect(screen.getByRole("button", { name: "Désactiver" })).toBeVisible();
  expect(screen.getByLabelText("Identifiant court")).toHaveAttribute(
    "pattern",
    "[a-z][a-z0-9_\\-]*",
  );
});
