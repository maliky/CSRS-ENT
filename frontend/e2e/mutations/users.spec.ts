import { expect, test } from "../support/test";

test("un compte désactivé apparaît dans les inactifs puis peut être réactivé", async ({
  page,
}) => {
  test.skip(
    process.env.CSRS_E2E_MUTATIONS !== "true",
    "Le scénario attend un jeu de données E2E préparé.",
  );
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  expect(dataset).toMatch(/^e2e-[a-z0-9-]+$/);
  const accountName = `[E2E:${dataset}] Parc automobile`;

  await page.goto("/app/administration/utilisateurs");
  await page.getByLabel("Recherche").fill(accountName);
  await page.getByRole("button", { name: "Appliquer" }).click();
  await page
    .getByRole("checkbox", { name: `Sélectionner ${accountName}` })
    .click();
  await page.getByRole("button", { name: "Désactiver" }).click();
  await page.getByRole("button", { name: "Confirmer" }).click();

  await expect(page.getByLabel("État")).toHaveValue("inactive");
  await expect(page.getByRole("link", { name: accountName })).toBeVisible();
  await expect(page.getByText("Inactif")).toBeVisible();

  await page.getByRole("link", { name: accountName }).click();
  await page.getByRole("button", { name: "Réactiver" }).click();
  await expect(page.getByRole("status")).toContainText("Compte réactivé.");
  await expect(page.getByRole("button", { name: "Désactiver" })).toBeVisible();
});
