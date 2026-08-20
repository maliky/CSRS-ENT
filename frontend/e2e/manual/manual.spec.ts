import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

import { authenticateFixtureRole } from "../support/session";

const screenshotDir = resolve(process.cwd(), "../docs/screenshots");
const screenshotPath = (name: string) => resolve(screenshotDir, name);

test.beforeAll(async () => {
  await mkdir(screenshotDir, { recursive: true });
});

test("capture les nouveaux parcours du guide utilisateur", async ({ page }) => {
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  expect(dataset).toBe("e2e-manual");
  await authenticateFixtureRole(page, "agent");

  await page.goto("/app/equipe");
  await page
    .getByRole("link", { name: "Voir la fiche complète" })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Cahier des charges" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Modifier mon profil" }).click();
  await expect(page.getByLabel("Missions et responsabilités")).toBeVisible();
  await page.screenshot({
    path: screenshotPath("profil-cahier-des-charges.png"),
    fullPage: true,
  });

  await page.goto("/app/propositions");
  await page.getByRole("link", { name: "Nouvelle proposition" }).click();
  await expect(page.getByLabel("Charge estimée")).toBeVisible();
  await expect(page.getByLabel("Unité")).toHaveValue("hours");
  await page.screenshot({
    path: screenshotPath("charge-heures-ou-jours.png"),
    fullPage: true,
  });

  await page.goto("/app/projets");
  await page.getByRole("link", { name: "Ouvrir le projet" }).first().click();
  await expect(
    page.getByRole("button", { name: /2\. Plan d.action/ }),
  ).toBeVisible();
  await page.setViewportSize({ width: 2800, height: 1000 });
  await page.addStyleTag({
    content:
      "main, #contenu { max-width: none !important; width: 100% !important; }",
  });
  await page.screenshot({
    path: screenshotPath("projet-parcours-dix-etapes.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/app/procedures");
  const subject = `[E2E:${dataset}] Demande d'absence`;
  const card = page.getByRole("heading", { name: subject }).locator("xpath=..");
  await card.getByRole("link", { name: "Ouvrir le dossier" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: subject }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Soumettre/ })).toBeVisible();
  await page.screenshot({
    path: screenshotPath("procedure-dossier-et-circuit.png"),
    fullPage: true,
  });
});
