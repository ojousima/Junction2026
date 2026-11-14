import asyncio
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

with patch.dict("os.environ", {"DATABASE_URL": ""}):
    from infra.aiven.cloud import app as cloud


class StoreStub:
    def __init__(self, subscriptions):
        self.subs = subscriptions
        self.unsubscribed = []

    def subscriptions(self, device=None):
        return list(self.subs)

    def unsubscribe(self, endpoint):
        self.unsubscribed.append(endpoint)
        self.subs = [(device, sub) for device, sub in self.subs
                     if sub["endpoint"] != endpoint]


class CloudPushTests(unittest.TestCase):
    def test_ip_component_never_generates_alerts(self):
        store = MagicMock()
        store.subscriptions.return_value = [("device", {"endpoint": "https://push/sub"})]
        store.latest.return_value = {
            "fan": {"level": "ok", "text": "Fan OK"},
            "local_ip": {"level": "alert", "text": "10.0.38.191"},
        }
        store.alert_state.return_value = {}
        with patch.object(cloud, "store", store), patch.object(cloud, "VAPID_PRIVATE", "configured"), \
                patch.object(cloud, "push_alert") as push_alert, \
                patch.object(cloud.time, "sleep", side_effect=StopIteration), \
                self.assertRaises(StopIteration):
            cloud.push_loop()

        push_alert.assert_not_called()
        store.set_alert_state.assert_called_once_with("device", "fan", "ok")

    def test_send_push_distinguishes_success_expired_and_retry(self):
        class WebPushException(Exception):
            def __init__(self, status):
                self.response = types.SimpleNamespace(status_code=status)

        outcome = {"status": None}

        def webpush(**_kwargs):
            status = outcome["status"]
            if status is not None:
                raise WebPushException(status)

        module = types.ModuleType("pywebpush")
        module.WebPushException = WebPushException
        module.webpush = webpush
        sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/subscription"}
        with patch.dict(sys.modules, {"pywebpush": module}):
            self.assertEqual(cloud.send_push(sub, {}), "sent")
            for status in (404, 410):
                outcome["status"] = status
                self.assertEqual(cloud.send_push(sub, {}), "expired")
            for status in (429, 503):
                outcome["status"] = status
                self.assertEqual(cloud.send_push(sub, {}), "retry")

    def test_alert_retries_only_recipients_not_yet_handled(self):
        subscriptions = [
            ("device", {"endpoint": "https://push/sent"}),
            ("device", {"endpoint": "https://push/retry"}),
            ("device", {"endpoint": "https://push/expired"}),
        ]
        store = StoreStub(subscriptions)
        pending = {}
        attempts = []
        outcomes = iter(("sent", "retry", "expired", "sent"))

        def send(sub, _payload):
            attempts.append(sub["endpoint"])
            return next(outcomes)

        with patch.object(cloud, "store", store), patch.object(cloud, "send_push", side_effect=send):
            self.assertFalse(cloud.push_alert("device", "fan", "Fan problem", pending))
            self.assertEqual(set(pending[("device", "fan")]), {"https://push/retry"})
            self.assertEqual(store.unsubscribed, ["https://push/expired"])
            self.assertTrue(cloud.push_alert("device", "fan", "Fan problem", pending))

        self.assertEqual(attempts, [
            "https://push/sent", "https://push/retry", "https://push/expired",
            "https://push/retry",
        ])
        self.assertEqual(pending, {})

    def test_test_push_counts_only_successful_sends(self):
        device = cloud.Demo.DEVICE
        subscriptions = [
            (device, {"endpoint": "https://push/sent"}),
            (device, {"endpoint": "https://push/retry"}),
            (device, {"endpoint": "https://push/expired"}),
        ]
        store = StoreStub(subscriptions)
        outcomes = iter(("sent", "retry", "expired"))

        class RequestStub:
            async def json(self):
                return {"device": device}

        with patch.object(cloud, "store", store), patch.object(
            cloud, "VAPID_PRIVATE", "configured"
        ), patch.object(cloud, "send_push", side_effect=lambda *_: next(outcomes)):
            result = asyncio.run(cloud.api_push_test(RequestStub()))

        self.assertEqual(result, {"sent": 1})
        self.assertEqual(store.unsubscribed, ["https://push/expired"])


if __name__ == "__main__":
    unittest.main()
