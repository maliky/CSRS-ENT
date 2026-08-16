import { expect, test } from "../support/test";

async function authenticateFixtureSecretariat(
  page: import("@playwright/test").Page,
): Promise<void> {
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  const password = process.env.CSRS_E2E_FIXTURE_PASSWORD;
  expect(dataset).toMatch(/^e2e-[a-z0-9-]+$/);
  expect(password, "Le mot de passe du jeu E2E est requis").toBeTruthy();

  await page.goto("/app/");
  await page.getByRole("button", { name: "Déconnexion" }).click();
  await page
    .getByLabel(/identifiant/i)
    .fill(`${dataset}-secretariat@example.invalid`);
  await page.getByLabel("Mot de passe").fill(password!);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page.locator("#navigation-principale")).toBeVisible();
}

test("le compte secrétariat du jeu accède à la préparation des agendas", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );
  await authenticateFixtureSecretariat(page);

  await page.goto("/app/agenda");
  await expect(
    page.getByRole("heading", { level: 1, name: "Agendas de direction" }),
  ).toBeVisible();
  const direction = page.getByLabel("Direction de l’agenda");
  await expect(direction).toContainText("Direction administrative");
  await expect(direction).toContainText("Direction de la recherche");
  await expect(
    page.getByRole("button", { name: "Générer le PDF" }),
  ).toBeEnabled();
});

test("le secrétariat génère les agendas administration et recherche", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Les mutations nécessitent CSRS_E2E_MUTATIONS=true et un jeu de données E2E préparé.",
  );
  expect(process.env.CSRS_E2E_DATASET).toMatch(/^e2e-[a-z0-9-]+$/);
  await authenticateFixtureSecretariat(page);

  await page.goto("/app/agenda");
  for (const direction of ["Administration", "Direction de la recherche"]) {
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

test("un projet de recette expose ses neuf sections dans l'application", async ({
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

  const cycle = page.getByRole("region", { name: "Cycle des neuf onglets" });
  await expect(cycle.getByRole("heading", { level: 3 })).toHaveCount(9);
});
