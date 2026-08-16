import { expect, test } from "../support/test";

test("le menu mobile ouvre les parcours principaux puis restitue le focus", async ({
  page,
}) => {
  await page.goto("/app/");
  const open = page.getByRole("button", { name: "Ouvrir le menu" });
  await open.click();
  const navigation = page.locator("#navigation-principale");
  await expect(navigation).toBeVisible();
  await expect(
    navigation.getByRole("link", { name: "Mes tâches" }),
  ).toBeVisible();
  await expect(
    navigation.getByRole("link", { name: "Propositions" }),
  ).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Projets" })).toBeVisible();
  await page.getByRole("button", { name: "Fermer le menu" }).click();
  await expect(open).toBeFocused();
});
