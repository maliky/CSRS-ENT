from unittest import TestCase

from ..models.reporting import reporting_policy, rounded_percentage_average


class ReportingPolicyTests(TestCase):
    def test_preprod_refresh_allows_writes_and_marks_authoritative_refresh(self):
        policy = reporting_policy("preprod_refresh")

        self.assertTrue(policy.write_enabled)
        self.assertTrue(policy.authoritative_refresh)

    def test_unknown_mode_fails_closed(self):
        policy = reporting_policy("unexpected")

        self.assertEqual(policy.mode, "legacy_mirror")
        self.assertFalse(policy.write_enabled)

    def test_percentage_average_uses_half_up_rounding(self):
        self.assertEqual(rounded_percentage_average((66, 67)), 67)
