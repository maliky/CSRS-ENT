import { authenticateFixtureRole } from "../support/session";
import { expect, test } from "../support/test";

test("un agent retrouve son dossier d'absence et peut le soumettre", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  expect(dataset).toMatch(/^e2e-[a-z0-9-]+$/);
  const subject = `[E2E:${dataset}] Demande d'absence`;

  await test.step("Given un dossier d'absence appartenant à l'agent", async () => {
    await authenticateFixtureRole(page, "agent");
  });

  await test.step("When l'agent consulte les procédures", async () => {
    await page.goto("/app/procedures");
  });

  await test.step("Then son dossier est visible et l'action Soumettre lui appartient", async () => {
    const card = page
      .getByRole("heading", { name: subject })
      .locator("xpath=..");
    await card.getByRole("link", { name: "Ouvrir le dossier" }).click();
    await expect(
      page.getByRole("heading", { level: 1, name: subject }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /Soumettre/ })).toBeVisible();
  });
});

test("un agent ne peut pas contourner le menu pour administrer les comptes", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );

  await test.step("Given un agent sans le rôle Administration IT", async () => {
    await authenticateFixtureRole(page, "agent");
    await expect(page.getByRole("link", { name: "Utilisateurs" })).toHaveCount(
      0,
    );
  });

  await test.step("When il ouvre directement l'URL d'administration", async () => {
    await page.goto("/app/administration/utilisateurs");
  });

  await test.step("Then Odoo refuse l'accès et l'interface explique le refus", async () => {
    await expect(page.getByRole("alert")).toContainText(
      "Cette opération n'est pas autorisée.",
    );
    await expect(
      page.getByRole("button", { name: "Nouvel utilisateur" }),
    ).toHaveCount(0);
  });
});

test("un agent sélectionne l'organisation de recette sans la créer", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  const donor = `[E2E:${dataset}] Fondation partenaire`;

  await test.step("Given une organisation créée par l'administration IT", async () => {
    await authenticateFixtureRole(page, "agent");
  });

  await test.step("When l'agent ouvre la proposition de projet", async () => {
    await page.goto("/app/projets");
    await page.getByRole("link", { name: "Ouvrir le projet" }).click();
    await page
      .getByRole("button", { name: "Modifier la fiche projet" })
      .click();
  });

  await test.step("Then il choisit le bailleur existant sans saisie libre", async () => {
    const field = page.getByLabel("Bailleur");
    await expect(field.locator("option", { hasText: donor })).toHaveCount(1);
    await expect(field).toHaveValue(/\d+/);
  });
});
