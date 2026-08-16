import { describe, expect, test } from "vitest";
import type { ProjectSection } from "../../lib/api/types";
import {
  projectRecap,
  resolveProjectStage,
  stageIsUnlocked,
} from "./projectJourney";

function section(code: string, unlocked: boolean): ProjectSection {
  return {
    id: 1,
    code,
    label: code,
    sequence: 1,
    required: true,
    unlocked,
    state: "draft",
    revision: 1,
    correction_reason: "",
    ready: unlocked,
    readiness_message: "",
    recipient_label: "",
    capabilities: {
      submit: false,
      verify: false,
      correct: false,
      validate: false,
      close: false,
    },
  };
}

describe("parcours numéroté du projet", () => {
  test("renvoie à la fiche projet lorsqu'une étape demandée est verrouillée", () => {
    const sections = [section("project", true), section("finance", false)];

    expect(stageIsUnlocked("finance", sections, false)).toBe(false);
    expect(resolveProjectStage("finance", sections, false)).toBe("project");
    expect(resolveProjectStage("inconnue", sections, false)).toBe("project");
  });

  test("calcule le récapitulatif sans état ni effet externe", () => {
    const project = {
      action_plan: [{ progress: 100 }, { progress: 35 }],
      budget: [
        {
          planned_amount: 500,
          committed_amount: 200,
          actual_amount: 150,
          available_amount: 300,
        },
        {
          planned_amount: 100,
          committed_amount: 50,
          actual_amount: 25,
          available_amount: 50,
        },
      ],
    };

    expect(projectRecap(project)).toEqual({
      activities: 2,
      completedActivities: 1,
      planned: 600,
      committed: 250,
      actual: 175,
      available: 350,
    });
  });
});
