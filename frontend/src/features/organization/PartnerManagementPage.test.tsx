import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { PartnerManagementPage } from "./PartnerManagementPage";

test("l'administration IT crée puis archive une organisation sélectionnable", async () => {
  const user = userEvent.setup();
  let items = [
    {
      id: 41,
      name: "Université CSRS",
      email: "",
      phone: "",
      active: true,
      state_token: "state-41",
    },
  ];
  server.use(
    http.get("/api/v1/partners/", ({ request }) => {
      const state = new URL(request.url).searchParams.get("state") ?? "active";
      return HttpResponse.json({
        items: items.filter((item) => item.active === (state === "active")),
      });
    }),
    http.post("/api/v1/partners/", async ({ request }) => {
      const body = (await request.json()) as {
        name: string;
        email: string;
        phone: string;
      };
      const created = {
        id: 42,
        name: body.name,
        email: body.email,
        phone: body.phone,
        active: true,
        state_token: "state-42",
      };
      items = [...items, created];
      return HttpResponse.json(created, { status: 201 });
    }),
    http.patch("/api/v1/partners/41/", async ({ request }) => {
      const body = (await request.json()) as { active: boolean };
      items = items.map((item) =>
        item.id === 41
          ? { ...item, active: body.active, state_token: "state-43" }
          : item,
      );
      return HttpResponse.json(items[0]);
    }),
  );

  render(<PartnerManagementPage />);

  await user.type(await screen.findByLabelText("Nom"), "Fondation santé");
  await user.click(screen.getByRole("button", { name: "Créer" }));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Organisation créée.",
  );
  expect(screen.getByText("Fondation santé")).toBeInTheDocument();

  const university = screen
    .getByRole("heading", { name: "Université CSRS" })
    .closest("section");
  expect(university).not.toBeNull();
  await user.click(
    within(university as HTMLElement).getByRole("button", { name: "Archiver" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Organisation archivée.",
  );
  expect(screen.queryByText("Université CSRS")).not.toBeInTheDocument();
});
