import { expect, test } from "../support/test";
import { authenticateFixtureRole } from "../support/session";

test("le compte secrétariat du jeu accède à la préparation des agendas", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );
  await authenticateFixtureRole(page, "secretariat");

  await page.goto("/app/agenda");
  await expect(
    page.getByRole("heading", { level: 1, name: "Agendas de direction" }),
  ).toBeVisible();
  const direction = page.getByLabel("Direction de l’agenda");
  await expect(direction).toContainText("Direction administrative");
  await expect(direction).toContainText("Direction des programmes");
  await expect(
    page.getByRole("button", { name: "Générer le PDF" }),
  ).toBeEnabled();
});

test("le secrétariat génère les agendas administration et programmes", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Les mutations nécessitent CSRS_E2E_MUTATIONS=true et un jeu de données E2E préparé.",
  );
  expect(process.env.CSRS_E2E_DATASET).toMatch(/^e2e-[a-z0-9-]+$/);
  await authenticateFixtureRole(page, "secretariat");

  await page.goto("/app/agenda");
  for (const direction of [
    "Direction administrative",
    "Direction des programmes",
  ]) {
    await page
      .getByLabel("Agenda à préparer")
      .selectOption({ label: direction });
    await page.getByRole("button", { name: /Générer le PDF/ }).click();
    await expect(page.getByText(/PDF généré|Version .* créée/)).toBeVisible();
  }
});

test("l'organigramme ouvre le formulaire de l'unité sélectionnée", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  expect(dataset).toMatch(/^e2e-[a-z0-9-]+$/);

  await page.goto("/app/administration/organigramme");
  const row = page.getByRole("row").filter({
    hasText: `[E2E:${dataset}] Direction de recette`,
  });
  await row.getByRole("button", { name: "Modifier" }).click();

  await expect(
    page.getByRole("group", { name: "Modifier l’unité" }),
  ).toBeVisible();
  await expect(page.getByLabel("Code")).toBeFocused();
});

test("un projet de recette expose le parcours numéroté et ses étapes verrouillées", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  expect(dataset).toMatch(/^e2e-[a-z0-9-]+$/);

  await page.goto("/app/projets");
  const project = page.getByRole("heading", {
    name: `[E2E:${dataset}] Projet de recherche`,
  });
  const card = project.locator("xpath=..");
  await card.getByRole("link", { name: "Ouvrir le projet" }).click();

  const journey = page.getByRole("navigation", { name: "Parcours du projet" });
  await expect(journey.getByRole("button")).toHaveCount(10);
  await expect(
    journey.getByRole("button", { name: /1\. Projet/ }),
  ).toHaveAttribute("aria-current", "step");
  await expect(
    journey.getByRole("button", { name: /2\. Plan d’action/ }),
  ).toBeEnabled();
  await expect(
    journey.getByRole("button", { name: /3\. Résultats/ }),
  ).toBeDisabled();
});
