import { expectAccessible, expect, test } from "../support/test";

const routes = [
  ["/app/", "Mes tâches"],
  ["/app/equipe", "Synthèse de l'équipe"],
  ["/app/agenda", "Agendas de direction"],
  ["/app/absences", "Absences et missions"],
  ["/app/propositions", "Propositions de tâches"],
  ["/app/propositions/nouvelle", "Proposer une tâche"],
  ["/app/projets", "Projets de recherche"],
  ["/app/procedures", "Dossiers et visas"],
  ["/app/taches/nouvelle", "Affecter une tâche"],
  ["/app/administration/taches", "Gestion des tâches"],
  ["/app/administration/utilisateurs", "Utilisateurs"],
  ["/app/administration/organigramme", "Organigramme"],
] as const;

test.describe("routes fonctionnelles autorisées", () => {
  for (const [path, heading] of routes) {
    test(`${heading} se charge sans erreur serveur`, async ({ page }) => {
      const response = await page.goto(path);
      expect(response?.status()).toBeLessThan(500);
      await expect(
        page.getByRole("heading", { level: 1, name: heading }),
      ).toBeVisible();
      await expectAccessible(page);
    });
  }
});

test("tous les boutons visibles ont un nom accessible", async ({ page }) => {
  for (const [path, heading] of routes) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { level: 1, name: heading }),
    ).toBeVisible();
    const buttons = page.getByRole("button");
    for (let index = 0; index < (await buttons.count()); index += 1) {
      const button = buttons.nth(index);
      if (await button.isVisible()) {
        await expect(button).toHaveAccessibleName(/\S/);
      }
    }
  }
});

test("chaque saisie de date française propose aussi un calendrier", async ({
  page,
}) => {
  for (const path of ["/app/absences", "/app/propositions/nouvelle"]) {
    await page.goto(path);
    const dates = page.locator('input[placeholder="jj/mm/aaaa"]:visible');
    await expect(dates.first()).toBeVisible();
    const dateCount = await dates.count();
    for (let index = 0; index < dateCount; index += 1) {
      await expect(
        dates.nth(index).locator("xpath=..").locator('input[type="date"]'),
      ).toHaveCount(1);
    }
  }

  await page.goto("/app/projets");
  await page.getByRole("button", { name: "Nouvelle proposition" }).click();
  const projectDates = page.locator('input[placeholder="jj/mm/aaaa"]:visible');
  await expect(projectDates).toHaveCount(2);
});

test("la charge utilise les heures par défaut et conserve 1,5", async ({
  page,
}) => {
  await page.goto("/app/propositions/nouvelle");
  await expect(page.getByLabel("Unité")).toHaveValue("hours");
  const workload = page.getByLabel("Charge estimée");
  await workload.fill("1.5");
  await expect(workload).toHaveValue("1.5");
});

test("les listes administratives permettent de sélectionner toute la page", async ({
  page,
}) => {
  for (const path of [
    "/app/administration/utilisateurs",
    "/app/administration/taches",
  ]) {
    await page.goto(path);
    const selectAll = page.getByRole("checkbox", { name: "Tout sélectionner" });
    await expect(selectAll).toBeVisible();
    if (await selectAll.isEnabled()) {
      await selectAll.check();
      await expect(page.getByText(/sélectionné/)).not.toContainText("· 0 ");
      await selectAll.uncheck();
      const rows = page.locator('tbody input[type="checkbox"]:enabled');
      if ((await rows.count()) > 1) {
        await expect(rows.first()).not.toBeChecked();
        await rows.first().click();
        await expect(rows.first()).toBeChecked();
        await rows.last().click({ modifiers: ["Shift"] });
        await expect(rows.nth(1)).toBeChecked();
      }
    }
  }
});

test("une URL inexistante produit une erreur compréhensible", async ({
  page,
}) => {
  await test.step("Given une session utilisateur valide", async () => {
    await page.goto("/app/");
    await expect(page.locator("#navigation-principale")).toBeVisible();
  });

  await test.step("When l'utilisateur ouvre une page qui n'existe pas", async () => {
    await page.goto("/app/page-inexistante");
  });

  await test.step("Then l'interface explique que la page est indisponible", async () => {
    await expect(
      page.getByText("Cette page n'existe pas ou n'est plus accessible."),
    ).toBeVisible();
  });
});
