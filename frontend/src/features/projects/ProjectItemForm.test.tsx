import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { ResearchProjectDetail } from "../../lib/api/types";
import { ProjectItemForm } from "./ProjectItemForm";

test("saisit aussi la charge du plan d'action en heures par défaut", async () => {
  const user = userEvent.setup();
  render(
    <ProjectItemForm
      project={{ id: 7, revision: 3 } as ResearchProjectDetail}
      resource="action_plan"
      users={[
        { id: 4, name: "Agent", position: "Chercheur", login_alias: "agent" },
      ]}
      onSaved={vi.fn()}
      openLabel="Ouvrir le brouillon"
    />,
  );

  await user.click(screen.getByRole("button", { name: "Ouvrir le brouillon" }));

  expect(screen.getByRole("combobox", { name: "Unité" })).toHaveValue("hours");
  expect(screen.getByLabelText("Charge estimée")).toHaveValue(8);
  expect(screen.getByText("1 jour ouvré = 8 heures")).toBeVisible();
});
