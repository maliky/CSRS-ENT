from decimal import Decimal

import pytest

from gateway.serializers import (
    ProcessCreateSerializer,
    ProcessProcurementSerializer,
    ProcessQuotationSerializer,
    ProcessTransitionSerializer,
)


def test_bsf_requires_positive_amount_and_business_details() -> None:
    serializer = ProcessCreateSerializer(
        data={
            "process_type": "fund",
            "origin_department_id": 1,
            "project_id": 2,
            "subject": "Mission terrain",
            "description": "Décaissement",
            "amount": "200000.00",
            "details": {
                "budget_line_id": 3,
                "beneficiary_id": 4,
                "purpose": "Transport",
            },
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["amount"] == Decimal("200000.00")


@pytest.mark.parametrize("missing", ["budget_line_id", "quantity", "estimated_amount"])
def test_purchase_rejects_missing_requester_detail(missing: str) -> None:
    details = {
        "budget_line_id": 3,
        "quantity": 2,
        "estimated_amount": 300000,
    }
    details.pop(missing)
    serializer = ProcessCreateSerializer(
        data={
            "process_type": "purchase",
            "origin_department_id": 1,
            "project_id": 2,
            "subject": "Équipement",
            "description": "Achat",
            "amount": "300000.00",
            "details": details,
        }
    )

    assert not serializer.is_valid()
    assert "details" in serializer.errors


def test_quotation_requires_one_document() -> None:
    serializer = ProcessQuotationSerializer(
        data={
            "revision": 4,
            "vendor_id": 7,
            "reference": "DEVIS-7",
            "quotation_date": "2026-08-20",
            "amount": "280000.00",
            "documents": [],
        }
    )

    assert not serializer.is_valid()
    assert "documents" in serializer.errors


def test_procurement_payload_is_typed() -> None:
    serializer = ProcessProcurementSerializer(
        data={
            "revision": 5,
            "selected_quotation_id": 8,
            "product_id": 9,
            "quantity": 2,
            "negotiated_amount": "280000.00",
        }
    )

    assert serializer.is_valid(), serializer.errors


def test_evidence_transition_requires_stage_data() -> None:
    serializer = ProcessTransitionSerializer(
        data={"revision": 6, "action": "invoice"}
    )

    assert not serializer.is_valid()
    assert "stage_data" in serializer.errors
