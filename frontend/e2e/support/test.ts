import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test as base,
  type Page,
  type TestInfo,
} from "@playwright/test";

type BrowserDiagnostic = Readonly<{
  kind: "console" | "page" | "request" | "response";
  message: string;
}>;

function safePath(rawUrl: string): string {
  try {
    return new URL(rawUrl).pathname;
  } catch {
    return "URL invalide";
  }
}

async function attachDiagnostics(
  diagnostics: readonly BrowserDiagnostic[],
  testInfo: TestInfo,
) {
  if (diagnostics.length === 0) return;
  await testInfo.attach("diagnostics-navigateur.json", {
    body: Buffer.from(JSON.stringify(diagnostics, null, 2)),
    contentType: "application/json",
  });
}

export const test = base.extend<{ browserHealth: void }>({
  browserHealth: [
    async ({ page }, use, testInfo) => {
      const diagnostics: BrowserDiagnostic[] = [];
      page.on("console", (message) => {
        if (message.type() === "error") {
          diagnostics.push({ kind: "console", message: message.text() });
        }
      });
      page.on("pageerror", (error) => {
        diagnostics.push({ kind: "page", message: error.message });
      });
      page.on("requestfailed", (request) => {
        const failure = request.failure()?.errorText ?? "échec réseau";
        if (failure === "net::ERR_ABORTED") return;
        if (["document", "fetch", "xhr"].includes(request.resourceType())) {
          diagnostics.push({
            kind: "request",
            message: `${request.method()} ${safePath(request.url())} : ${failure}`,
          });
        }
      });
      page.on("response", (response) => {
        if (response.status() >= 500) {
          diagnostics.push({
            kind: "response",
            message: `${response.status()} ${safePath(response.url())}`,
          });
        }
      });

      await use();
      await attachDiagnostics(diagnostics, testInfo);
      expect(diagnostics, "Aucune erreur navigateur ou HTTP 5xx").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect } from "@playwright/test";

export async function expectAccessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const serious = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious, "Aucune violation d'accessibilité grave").toEqual([]);
}
