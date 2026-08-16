import { expect, test as setup } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";

const authFile = ".playwright/auth/dev.json";

setup(
  "authentifie le compte de recette sans exposer ses secrets",
  async ({ page }) => {
    const login = process.env.CSRS_E2E_LOGIN ?? "dev";
    const password = process.env.CSRS_E2E_PASSWORD;
    if (!password) {
      throw new Error(
        "CSRS_E2E_PASSWORD est requis. Utilisez scripts/test_preprod_e2e.sh pour lire le secret local sans l'afficher.",
      );
    }

    await page.goto("/app/");
    const loginField = page.getByLabel(/identifiant/i);
    const navigation = page.locator("#navigation-principale");
    await expect(loginField.or(navigation)).toBeVisible();
    if (await loginField.isVisible()) {
      await loginField.fill(login);
      await page.getByLabel("Mot de passe").fill(password);
      await page.getByRole("button", { name: "Se connecter" }).click();
    }

    await expect(page).toHaveURL(/\/app\//);
    await expect(navigation).toBeVisible();
    await mkdir(dirname(authFile), { recursive: true, mode: 0o700 });
    await page.context().storageState({ path: authFile });
  },
);
