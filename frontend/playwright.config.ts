import { defineConfig, devices } from "@playwright/test";

const baseURL =
  process.env.CSRS_E2E_BASE_URL ?? "https://preprod.ent.koba.sarl";
const target = new URL(baseURL);
const allowedHosts = new Set([
  "preprod.ent.koba.sarl",
  "127.0.0.1",
  "localhost",
]);

if (!allowedHosts.has(target.hostname)) {
  throw new Error(
    `Cible E2E refusée : ${target.hostname}. Utilisez une préproduction ou une instance locale explicitement autorisée.`,
  );
}

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results/e2e-artifacts",
  forbidOnly: Boolean(process.env.CI),
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: target.origin,
    locale: "fr-FR",
    timezoneId: "Etc/UTC",
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "authentication",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium-readonly",
      dependencies: ["authentication"],
      testMatch: /read-only\/.*\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: ".playwright/auth/dev.json",
      },
    },
    {
      name: "mobile-readonly",
      dependencies: ["authentication"],
      testMatch: /mobile\/.*\.spec\.ts/,
      use: {
        ...devices["Pixel 7"],
        storageState: ".playwright/auth/dev.json",
      },
    },
    {
      name: "chromium-mutations",
      dependencies: ["authentication"],
      testMatch: /mutations\/.*\.spec\.ts/,
      testIgnore: /mutations\/financial-processes\.spec\.ts/,
      fullyParallel: false,
      workers: 1,
      use: {
        ...devices["Desktop Chrome"],
        storageState: ".playwright/auth/dev.json",
      },
    },
    {
      name: "chromium-financial-processes",
      testMatch: /mutations\/financial-processes\.spec\.ts/,
      fullyParallel: false,
      workers: 1,
      retries: 0,
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
