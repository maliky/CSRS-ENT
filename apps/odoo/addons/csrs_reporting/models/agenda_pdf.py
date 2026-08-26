"""Pure ReportLab rendering for immutable CSRS ENT agenda snapshots."""

from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER, TA_LEFT  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    BalancedColumns,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

GREEN = colors.HexColor("#176B45")
PALE_GREEN = colors.HexColor("#EEF7F1")
LIGHT_BORDER = colors.HexColor("#BDD3C5")
MUTED = colors.HexColor("#52615A")
INK = colors.HexColor("#25352F")
REGULAR_FONT = "CsrsEntDejaVu"
BOLD_FONT = "CsrsEntDejaVuBold"


def _register_fonts() -> tuple[str, str]:
    fonts = (
        (REGULAR_FONT, Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")),
        (BOLD_FONT, Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    )
    for name, path in fonts:
        try:
            pdfmetrics.getFont(name)
        except KeyError:
            pdfmetrics.registerFont(TTFont(name, str(path)))
    return REGULAR_FONT, BOLD_FONT


def _text(value: object) -> str:
    return escape(str(value or ""))


def _date_text(value: object) -> str:
    raw = str(value or "")
    try:
        return date.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return _text(raw)


def _visitor_summary(rows: Sequence[Mapping[str, object]], empty: str) -> str:
    lines = []
    for row in rows:
        names = cast(Sequence[object], row.get("visitor_names") or ())
        label = ", ".join(_text(name) for name in names)
        if not label:
            label = f"{int(row.get('party_size') or 1)} visiteur(s)"
        lines.append(label)
    return "<br/>".join(lines) or empty


def _availability_summary(rows: Sequence[Mapping[str, object]]) -> str:
    lines = []
    for row in rows:
        employee = cast(Mapping[str, object], row.get("employee") or {})
        start = _date_text(row.get("start_date"))
        end = _date_text(row.get("end_date"))
        dates = start if start == end else f"{start} au {end}"
        note = f" - {_text(row.get('note'))}" if row.get("note") else ""
        lines.append(
            f"<b>{_text(row.get('kind_label'))}</b> : "
            f"{_text(employee.get('name'))} ({dates}){note}"
        )
    return "<br/>".join(lines) or "Aucune indisponibilité"


def render_agenda_pdf(
    snapshot: Mapping[str, object], *, generated_at: datetime, version: int
) -> bytes:
    """Render one frozen snapshot as a variable-height two-column A4 PDF."""
    regular, bold = _register_fonts()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "CsrsAgendaTitle",
        parent=styles["Title"],
        fontName=bold,
        fontSize=19,
        leading=23,
        textColor=GREEN,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    subtitle = ParagraphStyle(
        "CsrsAgendaSubtitle",
        parent=styles["Normal"],
        fontName=regular,
        fontSize=9,
        leading=12,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )
    box_title = ParagraphStyle(
        "CsrsAgendaBoxTitle",
        parent=styles["Normal"],
        fontName=bold,
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    box_body = ParagraphStyle(
        "CsrsAgendaBoxBody",
        parent=styles["Normal"],
        fontName=regular,
        fontSize=7.5,
        leading=10,
        textColor=INK,
        alignment=TA_CENTER,
    )
    unit_title = ParagraphStyle(
        "CsrsAgendaUnitTitle",
        parent=styles["Heading3"],
        fontName=bold,
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=TA_LEFT,
    )
    unit_body = ParagraphStyle(
        "CsrsAgendaUnitBody",
        parent=styles["BodyText"],
        fontName=regular,
        fontSize=7.4,
        leading=9.8,
        textColor=INK,
        alignment=TA_LEFT,
    )

    direction = str(snapshot.get("agenda_direction") or "")
    direction_label = _text(snapshot.get("agenda_direction_label"))
    document_title = (
        "Agenda DAF"
        if direction == "administration"
        else f"Agenda - {direction_label}"
    )
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=document_title,
        author="CSRS ENT",
    )
    story: list[object] = [
        Paragraph(document_title.upper(), title),
        Paragraph(
            f"Période du {_date_text(snapshot.get('period_start'))} "
            f"au {_date_text(snapshot.get('period_end'))}",
            subtitle,
        ),
    ]

    unclassified = cast(
        Sequence[Mapping[str, object]], snapshot.get("unclassified_users") or ()
    )
    if unclassified:
        names = ", ".join(_text(person.get("name")) for person in unclassified)
        story.extend(
            [
                Paragraph(
                    "Attention : personnes non classées incluses provisoirement "
                    f"dans tous les agendas : {names}",
                    unit_body,
                ),
                Spacer(1, 3 * mm),
            ]
        )

    arrivals = cast(Sequence[Mapping[str, object]], snapshot.get("arrivals") or ())
    departures = cast(
        Sequence[Mapping[str, object]], snapshot.get("departures") or ()
    )
    availability = cast(
        Sequence[Mapping[str, object]], snapshot.get("availability") or ()
    )
    summaries = (
        ("ÉVÉNEMENTS MAJEURS", _text(snapshot.get("major_events") or "RAS")),
        ("ARRIVÉES DE VISITEURS", _visitor_summary(arrivals, "Aucune arrivée")),
        ("DÉPARTS DE VISITEURS", _visitor_summary(departures, "Aucun départ")),
        ("CONGÉS, ABSENCES ET MISSIONS", _availability_summary(availability)),
    )
    boxes = []
    for label, body in summaries:
        boxes.append(
            Table(
                [[Paragraph(label, box_title)], [Paragraph(body, box_body)]],
                colWidths=[88 * mm],
                rowHeights=[9 * mm, None],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                        ("BACKGROUND", (0, 1), (-1, -1), PALE_GREEN),
                        ("BOX", (0, 0), (-1, -1), 0.6, LIGHT_BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                        ("TOPPADDING", (0, 1), (-1, -1), 3 * mm),
                        ("BOTTOMPADDING", (0, 1), (-1, -1), 3 * mm),
                    ]
                ),
            )
        )
    story.append(
        Table(
            [[boxes[0], boxes[1]], [boxes[2], boxes[3]]],
            colWidths=[90 * mm, 90 * mm],
            hAlign="CENTER",
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
                ]
            ),
        )
    )
    story.append(Spacer(1, 5 * mm))

    unit_cards: list[object] = []
    units = cast(Sequence[Mapping[str, object]], snapshot.get("units") or ())
    for unit in units:
        employee_rows = []
        employees = cast(Sequence[Mapping[str, object]], unit.get("employees") or ())
        for employee in employees:
            person = cast(Mapping[str, object], employee.get("person") or {})
            classification = (
                " <font color='#9B4D00'>(non classé)</font>"
                if employee.get("unclassified")
                else ""
            )
            lines = [
                f"<b>{_text(person.get('name'))}</b>{classification} - taux moyen : "
                f"<b>{int(employee.get('completion_rate') or 0)}%</b>"
            ]
            tasks = cast(Sequence[Mapping[str, object]], employee.get("tasks") or ())
            for task in tasks:
                delta = int(task.get("progress_delta") or 0)
                delta_text = f"+{delta}" if delta >= 0 else str(delta)
                observation = (
                    f" - {_text(task.get('observation'))}"
                    if task.get("observation")
                    else ""
                )
                lines.append(
                    f"• {_text(task.get('title'))} - "
                    f"<b>{int(task.get('percentage') or 0)}%</b> "
                    f"({delta_text} pt) - {_text(task.get('status_label'))}"
                    f"{observation}"
                )
            employee_rows.append([Paragraph("<br/>".join(lines), unit_body)])
        code = str(unit.get("code") or "").strip()
        name = str(unit.get("name") or "").strip()
        unit_label = f"{code} · {name}" if code else name
        card = Table(
            [
                [Paragraph(_text(unit_label), unit_title)],
                *(employee_rows or [[Paragraph("RAS", unit_body)]]),
            ],
            colWidths=[88 * mm],
            repeatRows=1,
            splitByRow=1,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.6, LIGHT_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            ),
        )
        unit_cards.extend([card, Spacer(1, 2 * mm)])

    if unit_cards:
        story.append(
            BalancedColumns(
                unit_cards,
                nCols=2,
                needed=30 * mm,
                innerPadding=2 * mm,
                leftPadding=0,
                rightPadding=0,
                topPadding=0,
                bottomPadding=0,
            )
        )
    else:
        story.append(
            Paragraph("Aucune tâche ouverte ou clôturée sur cette période.", unit_body)
        )

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(GREEN)
        canvas.setFont(bold, 8)
        canvas.drawString(12 * mm, A4[1] - 9 * mm, "CSRS ENT")
        canvas.setFillColor(MUTED)
        canvas.setFont(regular, 7)
        canvas.drawString(
            12 * mm,
            8 * mm,
            f"Version {version} - générée le {generated_at:%d/%m/%Y à %H:%M}",
        )
        canvas.drawRightString(A4[0] - 12 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    pdf = output.getvalue()
    if not pdf.startswith(b"%PDF") or not sha256(pdf).digest():
        raise ValueError("Le rendu de l'agenda n'est pas un PDF valide.")
    return pdf
