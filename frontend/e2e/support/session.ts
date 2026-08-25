import { expect, type Page } from "@playwright/test";

export type FixtureRole =
  | "agent"
  | "manager"
  | "secondary"
  | "hr"
  | "secretariat"
  | "dg"
  | "finance"
  | "procurement"
  | "compliance"
  | "data"
  | "fleet"
  | "it";

const MANUAL_ROLE_LOGINS: Readonly<Record<FixtureRole, string>> = {
  agent: "agent.demandeur@demo.invalid",
  manager: "responsable.principal@demo.invalid",
  secondary: "responsable.secondaire@demo.invalid",
  hr: "responsable.rh@demo.invalid",
  secretariat: "secretariat.direction@demo.invalid",
  dg: "direction.generale@demo.invalid",
  finance: "responsable.finance@demo.invalid",
  procurement: "responsable.achats@demo.invalid",
  compliance: "responsable.conformite@demo.invalid",
  data: "gestionnaire.donnees@demo.invalid",
  fleet: "responsable.parc@demo.invalid",
  it: "administration.it@demo.invalid",
};

export async function authenticateFixtureRole(
  page: Page,
  role: FixtureRole,
): Promise<void> {
  const dataset = process.env.CSRS_E2E_DATASET ?? "";
  const password = process.env.CSRS_E2E_FIXTURE_PASSWORD;
  expect(dataset).toMatch(/^e2e-[a-z0-9-]+$/);
  expect(password, "Le mot de passe du jeu E2E est requis").toBeTruthy();

  await page.goto("/app/");
  const status = await page.evaluate(
    async ({ login, fixturePassword }) => {
      const csrf =
        document.cookie
          .split(";")
          .map((item) => item.trim())
          .find((item) => item.startsWith("csrftoken="))
          ?.split("=", 2)[1] ?? "";
      const response = await fetch("/api/v1/session/login/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": decodeURIComponent(csrf),
        },
        body: JSON.stringify({ login, password: fixturePassword }),
      });
      return response.status;
    },
    {
      login:
        dataset === "e2e-manual"
          ? MANUAL_ROLE_LOGINS[role]
          : `${dataset}-${role}@example.invalid`,
      fixturePassword: password!,
    },
  );
  expect(status).toBe(200);
  await page.goto("/app/");
  await expect(page.locator("#navigation-principale")).toBeVisible();
}
