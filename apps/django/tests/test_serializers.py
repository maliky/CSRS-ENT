from gateway.serializers import PlanningPreviewSerializer, ScheduleSerializer


def test_schedule_accepts_a_fractional_hour_expressed_in_working_days() -> None:
    serializer = ScheduleSerializer(
        data={
            "start_date": "2026-08-17",
            "due_date": "2026-08-17",
            "estimated_work_days": "0.1875",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert str(serializer.validated_data["estimated_work_days"]) == "0.1875"


def test_planning_preview_accepts_a_fractional_hour_without_rounding() -> None:
    serializer = PlanningPreviewSerializer(
        data={
            "calendar_id": 1,
            "start_date": "2026-08-17",
            "source": "workload",
            "estimated_work_days": "0.1875",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert str(serializer.validated_data["estimated_work_days"]) == "0.1875"
