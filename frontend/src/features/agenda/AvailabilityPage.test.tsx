import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, vi } from "vitest";
import { server } from "../../mocks/server";
import type { AvailabilityOptions } from "../../lib/api/types";
import { AvailabilityPage } from "./AvailabilityPage";

const availability: AvailabilityOptions = {
  week_start: "2026-08-17",
  employees: [
    {
      id: 8,
      name: "Agent de recette",
      position: "Agent",
      email: "agent@csrs.example",
      unit: "Programmes",
    },
  ],
  kinds: [
    { value: "leave", label: "Congé" },
    { value: "absence", label: "Absence" },
    { value: "mission", label: "Mission" },
  ],
  items: [
    {
      id: 31,
      revision: 2,
      employee: {
        id: 8,
        name: "Agent de recette",
        position: "Agent",
      },
      kind: "mission",
      kind_label: "Mission",
      start_date: "2026-08-18",
      end_date: "2026-08-20",
      note: "Collecte terrain",
      cancelled_at: null,
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

test("conserve l’indisponibilité et explique un échec d’annulation", async () => {
  const user = userEvent.setup();
  vi.spyOn(window, "prompt").mockReturnValue("Mission maintenue");
  server.use(
    http.get("/api/v1/availability/", () => HttpResponse.json(availability)),
    http.post("/api/v1/availability/31/cancel/", () =>
      HttpResponse.json(
        {
          error: {
            code: "stale_revision",
            message: "Cette indisponibilité a déjà été modifiée.",
            fields: {},
          },
        },
        { status: 409 },
      ),
    ),
  );
  render(<AvailabilityPage />);

  await user.click(await screen.findByRole("button", { name: "Annuler" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Cette indisponibilité a déjà été modifiée.",
  );
  expect(screen.getByText(/Collecte terrain/)).toBeInTheDocument();
});
