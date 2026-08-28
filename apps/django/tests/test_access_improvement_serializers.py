from gateway.serializers import PasswordSerializer, ProposalWithdrawSerializer


def test_password_serializer_rejects_reusing_current_password() -> None:
    serializer = PasswordSerializer(
        data={
            "current_password": "same-password",
            "new_password": "same-password",
            "new_password_confirmation": "same-password",
        }
    )

    assert not serializer.is_valid()
    assert "new_password" in serializer.errors


def test_proposal_withdraw_serializer_accepts_an_empty_reason() -> None:
    serializer = ProposalWithdrawSerializer(data={"revision": 3, "reason": ""})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["reason"] == ""
