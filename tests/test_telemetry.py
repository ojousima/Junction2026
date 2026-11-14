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
    @patch.object(telemetry, "board_local_ip", return_value="10.0.38.191")
    @patch.object(telemetry, "load_dotenv")
    @patch.object(telemetry.Path, "is_file", return_value=True)
    @patch.object(telemetry, "execute_values")
    @patch.object(telemetry.time, "sleep", side_effect=[None, StopIteration])
    @patch.object(telemetry.psycopg2, "connect")
    def test_failed_connection_retries_and_closes_after_commit(
            self, connect, sleep, execute, is_file, load_dotenv, board_local_ip, hardware_serial):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        connect.side_effect = [telemetry.psycopg2.OperationalError("offline"), conn]
        with patch.dict(os.environ, {"PG_CONNINFO": "test", "PGSSLROOTCERT": "ca.pem"},
                        clear=True):
            with self.assertRaises(StopIteration):
                telemetry.run(lambda: (self.state, self.times))
        self.assertEqual(connect.call_count, 2)
        # measurements and health summary go in separate transactions
        self.assertEqual(execute.call_count, 2)
        self.assertIn("sensors.measurements", execute.call_args_list[0].args[1])
        self.assertIn("sensors.health_status", execute.call_args_list[1].args[1])
        self.assertEqual(execute.call_args_list[1].args[2][-1][2:],
                         ("local_ip", "ok", "10.0.38.191"))
        self.assertEqual(connect.call_args.kwargs["sslmode"], "verify-full")
        self.assertEqual(conn.__exit__.call_count, 2)
        conn.close.assert_called_once()

    def test_health_rows_one_per_component_with_stable_device_id(self):
        rows = telemetry.build_health_rows(self.state, self.timestamp, "serial-1", "10.0.38.191")
        self.assertEqual([r[2] for r in rows], ["coil", "fan", "compressor", "defrost", "local_ip"])
        self.assertTrue(all(r[0] == telemetry.device_id("serial-1") for r in rows))
        self.assertEqual(rows[-1][3:], ("ok", "10.0.38.191"))
        self.assertEqual(rows[3][3], "ok")  # 21.5 C, 45 %: no frost weather
        missing = telemetry.build_health_rows(self.state, self.timestamp, "serial-1", None)
        self.assertEqual(missing[-1][2:], ("local_ip", "unknown", ""))

    def test_no_health_rows_while_everything_is_unknown(self):
        self.assertEqual(telemetry.build_health_rows({"temp_c": None, "rh": None}, self.timestamp,
                                                     "serial-1"), [])

    def test_board_local_ip_reads_shared_host_address_and_rejects_bad_values(self):
        with patch.object(telemetry.Path, "read_text", side_effect=["10.0.38.191\nboot-id\n", "boot-id\n"]):
            self.assertEqual(telemetry.board_local_ip(), "10.0.38.191")
        for value in ("not-an-ip", "127.0.0.1", "169.254.1.1"):
            with self.subTest(value=value), patch.object(
                    telemetry.Path, "read_text", side_effect=[f"{value}\nboot-id\n", "boot-id\n"]):
                self.assertIsNone(telemetry.board_local_ip())
        with patch.object(telemetry.Path, "read_text", side_effect=["10.0.38.191\nold-boot\n", "boot-id\n"]):
            self.assertIsNone(telemetry.board_local_ip())
        with patch.object(telemetry.Path, "read_text", side_effect=FileNotFoundError):
            self.assertIsNone(telemetry.board_local_ip())


if __name__ == "__main__":
    unittest.main()
