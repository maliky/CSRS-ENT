import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.CSRS_MANUAL_BASE_URL ?? "http://127.0.0.1:18017";
const target = new URL(baseURL);

if (!new Set(["127.0.0.1", "localhost"]).has(target.hostname)) {
  throw new Error(
    `Cible des captures refusée : ${target.hostname}. Utilisez une instance locale isolée.`,
  );
}

export default defineConfig({
  testDir: "./e2e/manual",
  outputDir: "./test-results/manual-artifacts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: target.origin,
    viewport: { width: 1440, height: 1000 },
    locale: "fr-FR",
    timezoneId: "Etc/UTC",
    colorScheme: "light",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
