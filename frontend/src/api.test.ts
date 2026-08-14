import { expect, test } from "vitest";
import { parseSessionPayload } from "./api";

test("convertit une identité de session valide", () => {
  expect(
    parseSessionPayload({
      authenticated: true,
      user: { id: 7, login: "agent", name: "Agent Test" },
    }),
  ).toEqual({
    authenticated: true,
    user: { id: 7, login: "agent", name: "Agent Test" },
  });
});

test("refuse une identité de session non typée", () => {
  expect(() =>
    parseSessionPayload({
      authenticated: true,
      user: { id: "7", login: "agent", name: "Agent Test" },
    }),
  ).toThrow("Identité de session invalide");
});
