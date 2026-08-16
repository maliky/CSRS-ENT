import { expect, test } from "../support/test";

test("le menu mobile ouvre les parcours principaux puis restitue le focus", async ({
  page,
}) => {
  let open = page.getByRole("button", { name: "Ouvrir le menu" });
  const navigation = page.locator("#navigation-principale");

  await test.step("Given l'utilisateur consulte l'ENT sur mobile", async () => {
    await page.goto("/app/");
    open = page.getByRole("button", { name: "Ouvrir le menu" });
    await expect(open).toBeVisible();
  });

  await test.step("When il ouvre la navigation principale", async () => {
    await open.click();
  });

  await test.step("Then les parcours autorisés sont regroupés et accessibles", async () => {
    await expect(navigation).toBeVisible();
    await expect(
      navigation.getByRole("link", { name: "Mes tâches" }),
    ).toBeVisible();
    await expect(
      navigation.getByRole("link", { name: "Propositions" }),
    ).toBeVisible();
    await expect(
      navigation.getByRole("link", { name: "Projets" }),
    ).toBeVisible();
  });

  await test.step("And la fermeture restitue le focus au déclencheur", async () => {
    await navigation.getByRole("button", { name: "Fermer le menu" }).click();
    await expect(open).toBeFocused();
  });
});
