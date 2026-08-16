import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { OrganizationPage } from "./OrganizationPage";

test("le bouton Modifier ouvre et cible immédiatement le formulaire de l’unité", async () => {
  const user = userEvent.setup();
  server.use(
    http.get("/api/v1/organization/", () =>
      HttpResponse.json({
        units: [
          {
            id: 7,
            code: "RECH",
            short_name: "Recherche",
            long_name: "Direction de la recherche",
            label: "RECH — Recherche",
            kind: "direction",
            display_order: 2,
            parent_id: null,
            active: true,
            state_token: "unit-token",
          },
        ],
        grants: [],
        role_codes: [],
        users: [],
      }),
    ),
  );
  render(<OrganizationPage />);

  await user.click(await screen.findByRole("button", { name: "Modifier" }));

  expect(
    screen.getByRole("group", { name: "Modifier l’unité" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Code")).toHaveValue("RECH");
  expect(screen.getByLabelText("Code")).toHaveFocus();
});
