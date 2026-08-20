import { expect, test, type Page } from "@playwright/test";
import { authenticateFixtureRole, type FixtureRole } from "../support/session";

type ProcessDetail = Readonly<{
  id: number;
  reference: string;
  process_type: "fund" | "purchase";
  state: string;
  revision: number;
  presentation?: Readonly<{
    kind: string;
    payment_method?: string;
    payment_date?: string | null;
    quotations?: readonly Readonly<{ id: number }>[];
    purchase_order?: Readonly<{ id: number; name: string }> | null;
    evidence?: readonly Readonly<{ kind: string; reference: string }>[];
  }>;
}>;

type ProcessList = readonly ProcessDetail[];
type ProcessOptions = Readonly<{
  vendors: readonly Readonly<{ id: number; name: string }>[];
  products: readonly Readonly<{ id: number; name: string }>[];
}>;

const document = {
  name: "justificatif-recette.pdf",
  mimetype: "application/pdf",
  content_base64: Buffer.from("%PDF-1.4\n% CSRS ENT E2E\n").toString("base64"),
};

async function api<T>(
  page: Page,
  method: "GET" | "POST" | "PUT" | "PATCH",
  path: string,
  body?: object,
): Promise<T> {
  const response = await page.evaluate(
    async ({ requestMethod, requestPath, requestBody }) => {
      const csrf =
        document.cookie
          .split(";")
          .map((item) => item.trim())
          .find((item) => item.startsWith("csrftoken="))
          ?.split("=", 2)[1] ?? "";
      const result = await fetch(requestPath, {
        method: requestMethod,
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": decodeURIComponent(csrf),
        },
        body: requestBody ? JSON.stringify(requestBody) : undefined,
      });
      return { status: result.status, payload: await result.json() };
    },
    { requestMethod: method, requestPath: path, requestBody: body },
  );
  expect([200, 201]).toContain(response.status);
  return response.payload as T;
}

async function asRole(page: Page, role: FixtureRole): Promise<void> {
  await page.context().clearCookies();
  await authenticateFixtureRole(page, role);
}

function processRows(payload: unknown): ProcessList {
  if (Array.isArray(payload)) return payload as ProcessList;
  const container = payload as { results?: ProcessList; items?: ProcessList };
  return container.results ?? container.items ?? [];
}

async function seededProcess(
  page: Page,
  processType: "fund" | "purchase",
): Promise<ProcessDetail> {
  const payload = await api<unknown>(page, "GET", "/api/v1/processes/");
  const process = processRows(payload).find(
    (item) => item.process_type === processType,
  );
  expect(process, `Le dossier E2E ${processType} existe`).toBeTruthy();
  return process!;
}

async function detail(page: Page, processId: number): Promise<ProcessDetail> {
  return api<ProcessDetail>(page, "GET", `/api/v1/processes/${processId}/`);
}

async function transition(
  page: Page,
  process: ProcessDetail,
  action: string,
  extra: object = {},
): Promise<ProcessDetail> {
  return api<ProcessDetail>(
    page,
    "POST",
    `/api/v1/processes/${process.id}/transition/`,
    { revision: process.revision, action, ...extra },
  );
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function dgConfirmation(): string {
  const [year, month, day] = today().split("-");
  return `VALIDÉ LE ${day}/${month}/${year}`;
}

function latestPaymentDay(): string {
  const current = new Date(`${today()}T12:00:00Z`);
  while (![2, 4, 5].includes(current.getUTCDay())) {
    current.setUTCDate(current.getUTCDate() - 1);
  }
  return current.toISOString().slice(0, 10);
}

test("la DA produit un BC confirmé et trois preuves avant paiement", async ({
  page,
}) => {
  await asRole(page, "agent");
  let process = await seededProcess(page, "purchase");
  process = await transition(page, process, "submit");

  await asRole(page, "finance");
  process = await detail(page, process.id);
  process = await transition(page, process, "approve");

  await asRole(page, "dg");
  process = await detail(page, process.id);
  process = await transition(page, process, "approve", {
    confirmation: dgConfirmation(),
  });

  await asRole(page, "procurement");
  process = await detail(page, process.id);
  const options = await api<ProcessOptions>(
    page,
    "GET",
    "/api/v1/processes/options/",
  );
  const vendor = options.vendors[0];
  const product = options.products[0];
  expect(vendor).toBeTruthy();
  expect(product).toBeTruthy();
  process = await api<ProcessDetail>(
    page,
    "POST",
    `/api/v1/processes/${process.id}/quotations/`,
    {
      revision: process.revision,
      vendor_id: vendor!.id,
      reference: "COT-E2E-001",
      quotation_date: today(),
      amount: "300000.00",
      documents: [document],
    },
  );
  const quotation = process.presentation?.quotations?.[0];
  expect(quotation).toBeTruthy();
  process = await api<ProcessDetail>(
    page,
    "PUT",
    `/api/v1/processes/${process.id}/procurement/`,
    {
      revision: process.revision,
      selected_quotation_id: quotation!.id,
      product_id: product!.id,
      quantity: 2,
      negotiated_amount: "280000.00",
    },
  );
  process = await transition(page, process, "order");
  expect(process.presentation?.purchase_order?.name).toBeTruthy();

  for (const [action, reference] of [
    ["receive", "BL-E2E-001"],
    ["invoice", "FAC-E2E-001"],
  ] as const) {
    process = await transition(page, process, action, {
      stage_data: {
        reference,
        date: today(),
        evidence_date: today(),
        amount: action === "invoice" ? "280000.00" : 0,
        document,
      },
    });
  }

  await asRole(page, "finance");
  process = await detail(page, process.id);
  process = await transition(page, process, "pay", {
    stage_data: {
      reference: "PAY-E2E-001",
      date: today(),
      evidence_date: today(),
      amount: "280000.00",
      document,
    },
  });
  expect(process.state).toBe("completed");
  expect(process.presentation?.evidence?.map((item) => item.kind)).toEqual([
    "delivery",
    "invoice",
    "payment",
  ]);

  await page.goto(`/app/procedures/${process.id}`);
  await expect(page.getByText(process.reference)).toBeVisible();
  await expect(page.getByText("PAY-E2E-001")).toBeVisible();
});

test("le BSF est payé par le caissier un jour autorisé et non futur", async ({
  page,
}) => {
  await asRole(page, "agent");
  let process = await seededProcess(page, "fund");
  process = await transition(page, process, "submit");

  const route: readonly Readonly<{
    state: string;
    role: FixtureRole;
    confirmation?: boolean;
  }>[] = [
    { state: "finance_review", role: "finance" },
    { state: "requester_visa", role: "agent" },
    { state: "finance_head", role: "finance" },
    { state: "daf_review", role: "finance" },
    { state: "project_accounting", role: "finance" },
    { state: "dg_review", role: "dg", confirmation: true },
  ];
  for (const step of route) {
    expect(process.state).toBe(step.state);
    await asRole(page, step.role);
    process = await detail(page, process.id);
    process = await transition(
      page,
      process,
      "approve",
      step.confirmation ? { confirmation: dgConfirmation() } : {},
    );
  }

  await asRole(page, "finance");
  process = await detail(page, process.id);
  const paymentDate = latestPaymentDay();
  process = await transition(page, process, "pay", {
    stage_data: { payment_date: paymentDate },
  });
  expect(process.state).toBe("completed");
  expect(process.presentation?.payment_date).toBe(paymentDate);
  expect(process.presentation?.payment_method).toBeTruthy();

  await page.goto(`/app/procedures/${process.id}`);
  await expect(page.getByText(process.reference)).toBeVisible();
  await expect(page.getByText(paymentDate)).toBeVisible();
});
