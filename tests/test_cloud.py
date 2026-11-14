import base64
import binascii
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import requests

with patch.dict("os.environ", {"DATABASE_URL": ""}):
    from infra.aiven.cloud import app as cloud_app


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
        self.assertEqual(cloud_app.send_push(
            {"endpoint": "https://169.254.169.254/latest"}, {}), "expired")


class DatabaseTLSConfigurationTests(unittest.TestCase):
    def test_ca_diagnostics_report_source_and_format_without_contents(self):
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        raw_ca = "-----BEGIN CERTIFICATE-----\\nPRIVATE-TEST-CONTENT\\n-----END CERTIFICATE-----"
        encoded_ca = base64.b64encode(b"-----BEGIN CERTIFICATE-----\nOTHER\n"
                                      b"-----END CERTIFICATE-----").decode("ascii")
        with patch.dict(sys.modules, {"psycopg2": pg, "psycopg2.extras": pg.extras}), \
                patch.dict("os.environ", {"AIVEN_CA_CERT": raw_ca, "PROJECT_CA_CERT": encoded_ca}), \
                patch.object(cloud_app.tempfile, "NamedTemporaryFile"), \
                patch.object(cloud_app.Postgres, "run"), \
                patch("builtins.print") as log:
            cloud_app.Postgres("postgresql://example")

        messages = [call.args[0] for call in log.call_args_list]
        self.assertIn("source=AIVEN_CA_CERT", messages[0])
        self.assertIn("AIVEN_CA_CERT set=True, PROJECT_CA_CERT set=True", messages[0])
        self.assertIn("begin marker=True, end marker=True, line breaks=False, escaped newlines=True",
                      messages[1])
        self.assertNotIn("PRIVATE-TEST-CONTENT", " ".join(messages))
        self.assertNotIn(encoded_ca, " ".join(messages))

    def test_injected_project_ca_enables_server_verification(self):
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        encoded_ca = base64.b64encode(b"project CA\n").decode("ascii")
        with patch.dict(sys.modules, {"psycopg2": pg, "psycopg2.extras": pg.extras}), \
                patch.dict("os.environ", {"AIVEN_CA_CERT": "", "PROJECT_CA_CERT": encoded_ca}), \
                patch.object(cloud_app.tempfile, "NamedTemporaryFile") as tempfile, \
                patch.object(cloud_app.Postgres, "run") as run, \
                patch("builtins.print") as log:
            tempfile.return_value.name = "/tmp/project-ca.pem"
            db = cloud_app.Postgres("postgresql://example")

        self.assertIn("source=PROJECT_CA_CERT", log.call_args_list[0].args[0])
        tempfile.return_value.write.assert_called_once_with("project CA\n\n")
        self.assertEqual(db.kwargs, {"sslmode": "verify-full", "sslrootcert": "/tmp/project-ca.pem"})
        self.assertEqual(len(run.call_args_list), 3)
        self.assertTrue(all(call.args[0].startswith("SELECT ") for call in run.call_args_list))

    def test_invalid_injected_ca_fails_explicitly(self):
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        with patch.dict(sys.modules, {"psycopg2": pg, "psycopg2.extras": pg.extras}), \
                patch.dict("os.environ", {"AIVEN_CA_CERT": "", "PROJECT_CA_CERT": "not base64!"}), \
                self.assertRaises(binascii.Error):
            cloud_app.Postgres("postgresql://example")


class CloudStatusTests(unittest.TestCase):
    def test_status_uses_address_from_latest_health_row(self):
        now = datetime.now(timezone.utc)
        latest = {
            "coil": {"time": now - timedelta(seconds=1), "level": "ok",
                     "text": "OK"},
            "fan": {"time": now, "level": "ok", "text": "OK"},
            "local_ip": {"time": now, "level": "ok", "text": "10.0.38.191"},
        }
        with patch.object(cloud_app.store, "latest", return_value=latest):
            self.assertEqual(cloud_app.api_status(cloud_app.Demo.DEVICE)["local_ip"], "10.0.38.191")
            latest["local_ip"]["level"] = "unknown"
            self.assertIsNone(cloud_app.api_status(cloud_app.Demo.DEVICE)["local_ip"])
            latest["local_ip"].update(level="ok", time=now - timedelta(seconds=1))
            self.assertIsNone(cloud_app.api_status(cloud_app.Demo.DEVICE)["local_ip"])
            latest["local_ip"].update(level="alert", time=now + timedelta(days=1))
            status = cloud_app.api_status(cloud_app.Demo.DEVICE)
            self.assertEqual(status["overall"], "ok")
            self.assertEqual(status["last_seen"], now.isoformat())
            self.assertIsNone(status["local_ip"])

    def test_postgres_latest_includes_the_local_address(self):
        now = datetime.now(timezone.utc)
        rows = [{"component": "local_ip", "level": "ok", "message": "10.0.38.191",
                 "time": now}]
        db = cloud_app.Postgres.__new__(cloud_app.Postgres)
        with patch.object(db, "run", return_value=rows):
            self.assertEqual(db.latest(cloud_app.Demo.DEVICE)["local_ip"]["text"], "10.0.38.191")


if __name__ == "__main__":
    unittest.main()
