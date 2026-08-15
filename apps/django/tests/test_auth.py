from django.core.cache import cache
from django.test import SimpleTestCase

from gateway.auth import LoginRateLimiter, client_ip, normalize_login, rate_key


class AuthenticationCoreTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_login_normalization_is_deterministic(self) -> None:
        self.assertEqual(
            normalize_login(" Agent@Preprod.ENT.Koba.Sarl "),
            "agent@preprod.ent.koba.sarl",
        )

    def test_rate_keys_do_not_reveal_personal_values(self) -> None:
        key = rate_key("login", "person@example.org")

        self.assertNotIn("person", key)
        self.assertNotIn("example", key)

    def test_client_ip_accepts_a_valid_value_from_a_trusted_proxy(self) -> None:
        meta: dict[str, object] = {
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_X_REAL_IP": "203.0.113.7",
        }

        self.assertEqual(client_ip(meta, frozenset({"127.0.0.1"})), "203.0.113.7")

    def test_client_ip_ignores_headers_from_an_untrusted_peer(self) -> None:
        meta: dict[str, object] = {
            "REMOTE_ADDR": "198.51.100.9",
            "HTTP_X_REAL_IP": "203.0.113.7",
        }

        self.assertEqual(client_ip(meta, frozenset({"127.0.0.1"})), "198.51.100.9")

    def test_success_clears_both_rate_counters(self) -> None:
        limiter = LoginRateLimiter(cache)
        limiter.record_failure("127.0.0.1", "agent")

        limiter.clear("127.0.0.1", "agent")

        self.assertFalse(limiter.is_blocked("127.0.0.1", "agent"))
