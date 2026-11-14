import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
import telemetry


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.timestamp = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.state = {"temp_c": 21.5, "rh": 45.0}
        self.times = {"thermo": self.timestamp}

    def test_real_sensor_sample_and_stable_unique_id(self):
        measurements, included = telemetry.build_rows(self.state, self.times, {}, "serial-1")
        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0][1:], (self.timestamp, 21.5, 45.0))
        self.assertEqual(measurements[0][0], telemetry.sensor_id("serial-1", "thermo-1"))
        self.assertNotEqual(measurements[0][0], telemetry.sensor_id("serial-2", "thermo-1"))
        self.assertEqual(included, self.times)
        self.assertEqual(telemetry.build_rows(self.state, self.times, included, "serial-1"),
                         ([], {}))

    def test_missing_sensor_is_not_reported(self):
        self.state["temp_c"] = None
        self.assertEqual(telemetry.build_rows(self.state, self.times, {}, "serial-1"), ([], {}))
        self.state["temp_c"] = 21.5
        self.times["thermo"] = None
        self.assertEqual(telemetry.build_rows(self.state, self.times, {}, "serial-1"), ([], {}))

    def test_hardware_serial_is_required(self):
        with patch.object(telemetry.Path, "read_text", return_value=" 12345\n"):
            self.assertEqual(telemetry.hardware_serial(), "12345")
        with patch.object(telemetry.Path, "read_text", return_value="\n"):
            with self.assertRaises(ValueError):
                telemetry.hardware_serial()
        with patch.object(telemetry.Path, "read_text", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                telemetry.hardware_serial()

    @patch.object(telemetry, "hardware_serial", return_value="serial-1")
    @patch.object(telemetry, "load_dotenv")
    @patch.object(telemetry.Path, "is_file", return_value=True)
    @patch.object(telemetry, "execute_values")
    @patch.object(telemetry.time, "sleep", side_effect=[None, StopIteration])
    @patch.object(telemetry.psycopg2, "connect")
    def test_failed_connection_retries_and_closes_after_commit(
            self, connect, sleep, execute, is_file, load_dotenv, hardware_serial):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        connect.side_effect = [telemetry.psycopg2.OperationalError("offline"), conn]
        with patch.dict(os.environ, {"PG_CONNINFO": "test", "PGSSLROOTCERT": "ca.pem"},
                        clear=True):
            with self.assertRaises(StopIteration):
                telemetry.run(lambda: (self.state, self.times))
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(connect.call_args.kwargs["sslmode"], "verify-full")
        conn.__exit__.assert_called_once_with(None, None, None)
        conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
