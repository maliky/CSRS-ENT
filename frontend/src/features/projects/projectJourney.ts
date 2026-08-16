import type { ProjectSection } from "../../lib/api/types";

export const projectStageCodes = [
  "project",
  "action_plan",
  "results",
  "deliverables",
  "finance",
  "compliance",
  "risks",
  "reports",
  "closure",
  "recap",
] as const;

export type ProjectStageCode = (typeof projectStageCodes)[number];

export function isProjectStageCode(value: string): value is ProjectStageCode {
  return projectStageCodes.some((code) => code === value);
}

export function stageIsUnlocked(
  code: ProjectStageCode,
  sections: readonly ProjectSection[],
  recapUnlocked: boolean,
): boolean {
  if (code === "recap") return recapUnlocked;
  return sections.find((section) => section.code === code)?.unlocked ?? false;
}

export function resolveProjectStage(
  requested: string | null,
  sections: readonly ProjectSection[],
  recapUnlocked: boolean,
): ProjectStageCode {
  const candidate =
    requested && isProjectStageCode(requested) ? requested : "project";
  return stageIsUnlocked(candidate, sections, recapUnlocked)
    ? candidate
    : "project";
}

export type ProjectRecap = {
  activities: number;
  completedActivities: number;
  planned: number;
  committed: number;
  actual: number;
  available: number;
};

export function projectRecap(project: {
  action_plan: readonly { progress: number }[];
  budget: readonly {
    planned_amount: number;
    committed_amount: number;
    actual_amount: number;
    available_amount: number;
  }[];
}): ProjectRecap {
  return {
    activities: project.action_plan.length,
    completedActivities: project.action_plan.filter(
      (item) => item.progress >= 100,
    ).length,
    planned: project.budget.reduce(
      (total, item) => total + item.planned_amount,
      0,
    ),
    committed: project.budget.reduce(
      (total, item) => total + item.committed_amount,
      0,
    ),
    actual: project.budget.reduce(
      (total, item) => total + item.actual_amount,
      0,
    ),
    available: project.budget.reduce(
      (total, item) => total + item.available_amount,
      0,
    ),
  };
}
