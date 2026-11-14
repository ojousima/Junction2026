import unittest
from unittest.mock import patch

import requests

with patch.dict("os.environ", {"DATABASE_URL": ""}):
    from cloud import app as cloud_app


class PushEndpointTests(unittest.TestCase):
    def test_only_approved_https_push_service_origins_are_allowed(self):
        for endpoint in (
                "https://fcm.googleapis.com/fcm/send/subscription",
                "https://updates.push.services.mozilla.com/wpush/v2/subscription",
                "https://web.push.apple.com/subscription"):
            with self.subTest(endpoint=endpoint):
                self.assertTrue(cloud_app.valid_push_endpoint(endpoint))

    def test_rejects_unapproved_or_non_public_destinations(self):
        for endpoint in (
                "http://fcm.googleapis.com/subscription",
                "https://fcm.googleapis.com.attacker.example/subscription",
                "https://attacker.example/subscription",
                "https://127.0.0.1/subscription",
                "https://[::1]/subscription",
                "https://10.0.0.1/subscription",
                "https://169.254.169.254/latest",
                "https://user@fcm.googleapis.com/subscription",
                "https://fcm.googleapis.com:8443/subscription"):
            with self.subTest(endpoint=endpoint):
                self.assertFalse(cloud_app.valid_push_endpoint(endpoint))

    def test_push_requests_do_not_follow_redirects(self):
        session = cloud_app.push_requests_session()
        with patch.object(requests.Session, "request") as request:
            session.post("https://fcm.googleapis.com/subscription")
        self.assertFalse(request.call_args.kwargs["allow_redirects"])

    def test_existing_untrusted_subscription_is_not_sent(self):
        self.assertFalse(cloud_app.send_push(
            {"endpoint": "https://169.254.169.254/latest"}, {}))


if __name__ == "__main__":
    unittest.main()
