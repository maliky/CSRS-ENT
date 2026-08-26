"""Regression tests for flowing agenda cards in archived PDFs."""

from datetime import datetime
from io import BytesIO
from typing import Any

from PyPDF2 import PdfReader  # type: ignore[import-untyped]

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.agenda_pdf import render_agenda_pdf


@tagged("post_install", "-at_install")
class CsrsAgendaPdfTests(TransactionCase):
    def test_uneven_unit_cards_flow_through_two_independent_columns(self):
        def unit(letter: str, task_count: int) -> dict[str, object]:
            return {
                "id": ord(letter),
                "code": f"U-{letter}",
                "name": f"UNIT {letter}",
                "employees": [
                    {
                        "person": {"name": f"Agent {letter}"},
                        "unclassified": False,
                        "completion_rate": 40,
                        "tasks": [
                            {
                                "title": f"Tâche {letter}-{index}",
                                "percentage": index * 10,
                                "progress_delta": index,
                                "status_label": "En cours",
                                "observation": "",
                            }
                            for index in range(1, task_count + 1)
                        ],
                    }
                ],
            }

        snapshot = {
            "schema_version": 1,
            "period_start": "2026-08-17",
            "period_end": "2026-08-23",
            "agenda_direction": "administration",
            "agenda_direction_label": "Agenda DAF",
            "major_events": "Réunion de coordination",
            "unclassified_users": [],
            "arrivals": [],
            "departures": [],
            "availability": [],
            "units": [
                unit("A", 4),
                unit("B", 1),
                unit("C", 3),
                unit("D", 5),
                unit("E", 1),
                unit("F", 2),
            ],
        }

        pdf = render_agenda_pdf(
            snapshot, generated_at=datetime(2026, 8, 17, 8, 30), version=3
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        reader = PdfReader(BytesIO(pdf))
        self.assertGreaterEqual(len(reader.pages), 1)

        positions: dict[str, tuple[float, float]] = {}

        def capture_position(
            text: str,
            current_matrix: Any,
            text_matrix: Any,
            _font: Any,
            _font_size: Any,
        ) -> None:
            normalized = " ".join(text.split())
            for letter in "ABCDEF":
                label = f"U-{letter} · UNIT {letter}"
                if label in normalized:
                    x = (
                        text_matrix[4] * current_matrix[0]
                        + text_matrix[5] * current_matrix[2]
                        + current_matrix[4]
                    )
                    y = (
                        text_matrix[4] * current_matrix[1]
                        + text_matrix[5] * current_matrix[3]
                        + current_matrix[5]
                    )
                    positions[label] = (
                        float(x),
                        float(y),
                    )

        for page in reader.pages:
            page.extract_text(visitor_text=capture_position)

        self.assertEqual(len(positions), 6)
        x_values = [position[0] for position in positions.values()]
        self.assertGreater(max(x_values) - min(x_values), 150)
        self.assertAlmostEqual(
            positions["U-A · UNIT A"][0],
            positions["U-B · UNIT B"][0],
            delta=5,
        )
        self.assertNotAlmostEqual(
            positions["U-A · UNIT A"][1],
            positions["U-B · UNIT B"][1],
            delta=5,
        )
