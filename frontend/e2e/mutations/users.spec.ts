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

  await test.step("Given un compte actif réservé au jeu de recette", async () => {
    await page.goto("/app/administration/utilisateurs");
    await page.getByLabel("Recherche").fill(accountName);
    await page.getByRole("button", { name: "Appliquer" }).click();
    await expect(page.getByRole("link", { name: accountName })).toBeVisible();
  });

  await test.step("When l'administrateur désactive le compte", async () => {
    await page
      .getByRole("checkbox", { name: `Sélectionner ${accountName}` })
      .click();
    await page.getByRole("button", { name: "Désactiver" }).click();
    await page.getByRole("button", { name: "Confirmer" }).click();
  });

  await test.step("Then le compte apparaît parmi les comptes inactifs", async () => {
    await expect(page.getByLabel("État")).toHaveValue("inactive");
    await expect(page.getByRole("link", { name: accountName })).toBeVisible();
    await expect(page.getByText("Inactif", { exact: true })).toBeVisible();
  });

  await test.step("And il peut être réactivé sans perdre sa fiche", async () => {
    await page.getByRole("link", { name: accountName }).click();
    await page.getByRole("button", { name: "Réactiver" }).click();
    await expect(page.getByRole("status")).toContainText("Compte réactivé.");
    await expect(
      page.getByRole("button", { name: "Désactiver" }),
    ).toBeVisible();
  });
});
