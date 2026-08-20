import { createHash } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { authenticateFixtureRole } from "../support/session";

const screenshotDir = resolve(process.cwd(), "../docs/screenshots");
const dataset = process.env.CSRS_E2E_DATASET ?? "";
const marker = `[E2E:${dataset}]`;

function screenshotPath(name: string): string {
  return resolve(screenshotDir, name);
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function fixtureWeekStart(): string {
  const offset =
    createHash("sha256").update(dataset).digest().readUInt16BE(0) % 2500;
  const start = new Date(Date.UTC(2090, 0, 2 + offset, 12));
  const dayFromMonday = (start.getUTCDay() + 6) % 7;
  start.setUTCDate(start.getUTCDate() - dayFromMonday);
  return isoDate(start);
}

async function capture(page: Page, name: string): Promise<void> {
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation: none !important; transition: none !important; }",
  });
  await page.screenshot({ path: screenshotPath(name), fullPage: true });
}

test.beforeAll(async () => {
  expect(dataset).toBe("e2e-manual");
  await mkdir(screenshotDir, { recursive: true });
});

test.describe.configure({ mode: "serial" });

test("capture la connexion et les navigations selon le rôle", async ({
  page,
}) => {
  await page.goto("/app/");
  await expect(
    page.getByRole("heading", { name: "Connexion à CSRS ENT" }),
  ).toBeVisible();
  await capture(page, "01-connexion.png");

  await authenticateFixtureRole(page, "agent");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Ouvrir le menu" }).click();
  await expect(page.locator("#navigation-principale")).toBeVisible();
  await capture(page, "02-navigation-mobile-agent.png");

  await page.setViewportSize({ width: 1440, height: 1000 });
  await authenticateFixtureRole(page, "it");
  await expect(page.getByRole("link", { name: "Organisations" })).toBeVisible();
  await capture(page, "03-navigation-it.png");
});

test("capture le travail personnel, les propositions et les décisions du responsable", async ({
  page,
}) => {
  await authenticateFixtureRole(page, "agent");
  await page.goto("/app/?month=2095-01");
  await expect(page.getByRole("heading", { name: "Mes tâches" })).toBeVisible();
  const taskLink = page
    .getByRole("link", { name: /Tâche de recette 1/ })
    .first();
  await expect(taskLink).toBeVisible();
  const taskHref = await taskLink.getAttribute("href");
  expect(taskHref).toBeTruthy();
  await capture(page, "04-dashboard-agent.png");

  await taskLink.click();
  await expect(
    page.getByRole("heading", { name: /Tâche de recette 1/ }),
  ).toBeVisible();
  await capture(page, "05-tache-detail.png");
  await page.getByLabel(/Avancement/).fill("20");
  await page
    .getByLabel("Observation", { exact: true })
    .first()
    .fill("Précision fictive pour illustrer la progression.");
  await capture(page, "06-progression-observation.png");
  await page.getByLabel(/Avancement/).fill("100");
  await page
    .getByRole("button", { name: "Enregistrer la progression" })
    .click();
  await expect(
    page.getByText("Progression enregistrée à 100 %."),
  ).toBeVisible();

  await page.goto("/app/propositions/nouvelle");
  await expect(
    page.getByRole("heading", { name: "Proposer une tâche" }),
  ).toBeVisible();
  await capture(page, "08-proposition-form.png");

  await page.goto("/app/equipe");
  await page
    .getByRole("link", { name: "Voir la fiche complète" })
    .first()
    .click();
  await page.getByRole("button", { name: "Modifier mon profil" }).click();
  await expect(page.getByLabel("Missions et responsabilités")).toBeVisible();
  await capture(page, "12-profil-employe.png");

  await authenticateFixtureRole(page, "manager");
  await page.goto(taskHref!);
  await expect(
    page.getByRole("button", { name: "Valider l'achèvement" }),
  ).toBeVisible();
  await capture(page, "07-validation-tache-manager.png");

  await page.goto("/app/propositions");
  await expect(
    page.getByText(`${marker} Proposition de recette`),
  ).toBeVisible();
  await capture(page, "09-proposition-review.png");

  await page.goto("/app/taches/nouvelle");
  await expect(
    page.getByRole("heading", { name: "Affecter une tâche" }),
  ).toBeVisible();
  await capture(page, "10-affecter-tache.png");

  await page.goto("/app/equipe?month=2095-01");
  await expect(
    page.getByRole("heading", { name: "Synthèse de l'équipe" }),
  ).toBeVisible();
  await capture(page, "11-equipe-manager.png");
});

test("capture les absences et les agendas de direction", async ({ page }) => {
  const weekStart = fixtureWeekStart();
  const currentMonday = new Date(`${weekStart}T12:00:00Z`);
  const previousMonday = new Date(`${weekStart}T12:00:00Z`);
  previousMonday.setUTCDate(previousMonday.getUTCDate() - 7);
  await page.clock.setFixedTime(currentMonday);

  await authenticateFixtureRole(page, "hr");
  await page.goto(`/app/absences?week=${weekStart}`);
  await expect(
    page.getByRole("heading", { name: "Absences et missions" }),
  ).toBeVisible();
  await expect(page.getByText(`${marker} Mission de recette`)).toBeVisible();
  await capture(page, "13-absences-rh.png");

  await page.clock.setFixedTime(previousMonday);
  await authenticateFixtureRole(page, "secretariat");
  await page.goto("/app/agenda");
  await expect(
    page.getByRole("heading", { name: "Agendas de direction" }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Éléments à faire apparaître en tête du rapport"),
  ).toHaveValue(`${marker} Réunion de coordination`);
  await capture(page, "14-agenda-secretariat.png");

  await page.getByLabel("Direction de l’agenda").selectOption("research");
  await expect(
    page.getByRole("heading", { name: /Direction de la recherche/ }),
  ).toBeVisible();
  await capture(page, "15-agenda-apercu.png");
  await page.getByRole("button", { name: "Générer le PDF" }).click();
  await expect(
    page.getByText(/version PDF.*archivée|Odoo est indisponible/),
  ).toBeVisible();

  await authenticateFixtureRole(page, "dg");
  await page.goto("/app/agenda");
  await expect(
    page.getByRole("heading", { name: "Agendas archivés" }),
  ).toBeVisible();
  await capture(page, "16-agenda-archives.png");
});

test("capture le parcours complet d'un projet de recherche", async ({
  page,
}) => {
  await authenticateFixtureRole(page, "agent");
  await page.goto("/app/projets");
  await expect(
    page.getByRole("heading", { name: "Projets de recherche" }),
  ).toBeVisible();
  await capture(page, "17-projets-listes.png");

  await page.getByRole("button", { name: "Nouvelle proposition" }).click();
  await expect(
    page.getByRole("heading", { name: "Proposer un projet" }),
  ).toBeVisible();
  await capture(page, "18-projet-proposition.png");
  await page.getByRole("button", { name: "Annuler" }).click();

  await page.getByRole("link", { name: "Ouvrir le projet" }).first().click();
  await expect(
    page.getByRole("button", { name: /2\. Plan d.action/ }),
  ).toBeVisible();
  await page.setViewportSize({ width: 2400, height: 1000 });
  await page.addStyleTag({
    content:
      "main, #contenu { max-width: none !important; width: 100% !important; }",
  });
  await capture(page, "19-projet-parcours.png");

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: /2\. Plan d.action/ }).click();
  await page.getByRole("button", { name: "Ouvrir le brouillon" }).click();
  await expect(page.getByLabel("Activité")).toBeVisible();
  await capture(page, "20-projet-plan-action.png");
  await page.getByLabel("Activité").fill(`${marker} Activité documentée`);
  await page.getByLabel("Responsable").selectOption({ index: 1 });
  await page.locator("#action_plan-csrs_start_date").fill("03/01/2095");
  await page.locator("#action_plan-date_deadline").fill("10/01/2095");
  await page.getByLabel("Charge estimée").fill("8");
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await expect(page.getByText(`${marker} Activité documentée`)).toBeVisible();

  await page.getByRole("button", { name: /5\. Finances/ }).click();
  await page.getByRole("button", { name: "Ouvrir le brouillon" }).click();
  await expect(page.getByLabel("Code budgétaire")).toBeVisible();
  await capture(page, "21-projet-finances.png");
  await page.getByLabel("Code budgétaire").fill("E2E-BUD");
  await page.getByLabel("Ligne budgétaire").fill("Budget de démonstration");
  await page.getByLabel("Montant prévu").fill("250000");
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await expect(page.getByText("Budget de démonstration")).toBeVisible();
  await capture(page, "22-projet-controles-section.png");

  await authenticateFixtureRole(page, "it");
  await page.goto("/app/projets");
  await page.getByRole("button", { name: "À superviser" }).click();
  await page.getByRole("link", { name: "Ouvrir le projet" }).first().click();
  await expect(page.getByRole("button", { name: "Archiver" })).toBeVisible();
  await capture(page, "23-projet-supervision.png");
});

test("capture la création, le traitement et l'audit d'une procédure", async ({
  page,
}) => {
  await authenticateFixtureRole(page, "agent");
  await page.goto("/app/procedures");
  await page.getByRole("button", { name: "Nouveau dossier" }).click();
  await page.getByLabel("Procédure").selectOption("data");
  await expect(page.getByLabel("Objectifs de l’étude")).toBeVisible();
  await capture(page, "24-procedure-formulaire.png");

  const subject = `${marker} Demande d'absence`;
  const card = page.getByRole("heading", { name: subject }).locator("xpath=..");
  await card.getByRole("link", { name: "Ouvrir le dossier" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: subject }),
  ).toBeVisible();
  await capture(page, "25-procedure-dossier.png");
  await page
    .getByRole("heading", { name: "Historique audité" })
    .scrollIntoViewIfNeeded();
  await capture(page, "26-procedure-historique.png");
});

test("capture les outils de l'administration IT", async ({ page }) => {
  await authenticateFixtureRole(page, "it");

  await page.goto("/app/administration/taches");
  await expect(
    page.getByRole("heading", { name: "Gestion des tâches" }),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: /Sélectionner/ })
    .first()
    .click();
  await page.getByRole("button", { name: /Supprimer \(1\)/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await capture(page, "27-admin-taches.png");

  await page.goto("/app/administration/utilisateurs");
  await expect(
    page.getByRole("heading", { name: "Utilisateurs" }),
  ).toBeVisible();
  const fixtureUser = page
    .getByRole("link", { name: `${marker} Agent` })
    .first();
  await expect(fixtureUser).toBeVisible();
  const fixtureUserHref = await fixtureUser.getAttribute("href");
  expect(fixtureUserHref).toBeTruthy();
  await capture(page, "28-admin-utilisateurs.png");

  await page.goto(fixtureUserHref!);
  await expect(
    page.getByRole("heading", { name: `${marker} Agent` }),
  ).toBeVisible();
  await capture(page, "29-admin-utilisateur-form.png");

  await page.goto("/app/administration/organigramme");
  await expect(
    page.getByRole("heading", { name: "Organigramme" }),
  ).toBeVisible();
  await capture(page, "30-admin-organigramme.png");

  await page.goto("/app/administration/organisations");
  await expect(
    page.getByRole("heading", { name: "Organisations" }),
  ).toBeVisible();
  await capture(page, "31-admin-organisations.png");
});
