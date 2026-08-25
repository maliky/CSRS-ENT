import { describe, expect, it } from "vitest";

import { sectionStateLabel } from "../projects/ResearchProjectDetailPage";
import { ACTION_LABELS, EVIDENCE_LABELS } from "./ProcessDetailPage";

describe("libellés français des dossiers métier", () => {
  it("traduit les événements propres au traitement des achats", () => {
    expect(ACTION_LABELS.quotation).toBe("Cotation ajoutée");
    expect(ACTION_LABELS.procurement_update).toBe(
      "Préparation d'achat enregistrée",
    );
  });

  it("traduit les preuves et les états de section visibles", () => {
    expect(EVIDENCE_LABELS).toMatchObject({
      delivery: "Livraison",
      invoice: "Facture",
      payment: "Paiement",
    });
    expect(sectionStateLabel("draft")).toBe("Brouillon");
    expect(sectionStateLabel("correction")).toBe("À corriger");
  });
});
