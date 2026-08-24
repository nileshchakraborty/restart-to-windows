import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import main


def result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class PluginManifestTests(unittest.TestCase):
    def test_backend_does_not_request_root_or_development_flags(self):
        manifest_path = Path(__file__).resolve().parents[1] / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["flags"], [])


class DetectSupportTests(unittest.TestCase):
    def test_searches_only_the_system_command_path(self):
        with (
            patch.object(main, "system_command_path", return_value="/trusted/bin"),
            patch.object(main.shutil, "which", return_value="/trusted/bin/boot-windows") as which,
        ):
            helper, error = main.detect_support()

        self.assertEqual(helper, "/trusted/bin/boot-windows")
        self.assertIsNone(error)
        which.assert_called_once_with("boot-windows", path="/trusted/bin")

    def test_reports_the_supported_setup_command_when_helper_is_missing(self):
        with patch.object(main, "find_boot_windows", return_value=None):
            helper, error = main.detect_support()

        self.assertIsNone(helper)
        self.assertIn(main.SETUP_COMMAND, error)


class BootTargetVerificationTests(unittest.TestCase):
    def test_parses_exact_windows_entry_and_bootnext(self):
        output = "BootNext: 00af\nBoot00AF* Windows Boot Manager\tHD(...)\n"

        self.assertEqual(main.parse_windows_boot_targets(output), {"00AF"})
        self.assertEqual(main.parse_boot_next(output), "00AF")

    def test_rejects_similar_windows_entry_name(self):
        output = "Boot00AF* Windows Boot Manager Backup\n"

        self.assertEqual(main.parse_windows_boot_targets(output), set())

    def test_accepts_the_exact_windows_entry_selected_from_duplicates(self):
        output = (
            "BootNext: 00B0\n"
            "Boot00AF* Windows Boot Manager\tHD(first)\n"
            "Boot00B0* Windows Boot Manager\tHD(second)\n"
        )
        with (
            patch.object(main, "find_system_command", return_value="/trusted/efibootmgr"),
            patch.object(main, "run_command", return_value=result(stdout=output)),
        ):
            armed, error = main.windows_is_armed()

        self.assertTrue(armed)
        self.assertIsNone(error)

    def test_verifies_matching_windows_target(self):
        output = "BootNext: 00AF\nBoot00AF* Windows Boot Manager\tHD(...)\n"
        with (
            patch.object(main, "find_system_command", return_value="/trusted/efibootmgr"),
            patch.object(main, "run_command", return_value=result(stdout=output)),
        ):
            armed, error = main.windows_is_armed()

        self.assertTrue(armed)
        self.assertIsNone(error)

    def test_rejects_non_windows_bootnext(self):
        output = "BootNext: 0001\nBoot00AF* Windows Boot Manager\tHD(...)\n"
        with (
            patch.object(main, "find_system_command", return_value="/trusted/efibootmgr"),
            patch.object(main, "run_command", return_value=result(stdout=output)),
        ):
            armed, error = main.windows_is_armed()

        self.assertFalse(armed)
        self.assertIn("not the verified", error)


class RestartToWindowsTests(unittest.IsolatedAsyncioTestCase):
    async def test_support_does_not_expose_the_resolved_helper_path(self):
        plugin = main.Plugin()
        with patch.object(
            main, "detect_support", return_value=("/trusted/bin/boot-windows", None)
        ):
            self.assertEqual(await plugin.get_restart_support(), {"available": True})

    async def test_rechecks_support_before_restart(self):
        plugin = main.Plugin()
        with (
            patch.object(main, "detect_support", return_value=(None, "missing")),
            patch.object(main, "run_command") as run,
        ):
            response = await plugin.prepare_restart_to_windows()

        self.assertEqual(response, {"ok": False, "error": "missing"})
        run.assert_not_called()

    async def test_delegates_the_complete_operation_to_bazzite(self):
        plugin = main.Plugin()
        with (
            patch.object(
                main,
                "detect_support",
                return_value=("/trusted/bin/boot-windows", None),
            ),
            patch.object(main, "run_command", return_value=result()) as run,
            patch.object(main, "windows_is_armed", return_value=(True, None)),
        ):
            response = await plugin.prepare_restart_to_windows()

        self.assertEqual(response, {"ok": True})
        run.assert_called_once_with(["/trusted/bin/boot-windows"])

    async def test_accepts_helper_failure_when_windows_is_verified(self):
        plugin = main.Plugin()
        with (
            patch.object(
                main,
                "detect_support",
                return_value=("/trusted/bin/boot-windows", None),
            ),
            patch.object(
                main,
                "run_command",
                return_value=result(1, stderr="Cannot find Windows boot in EFI"),
            ),
            patch.object(main, "windows_is_armed", return_value=(True, None)),
        ):
            response = await plugin.prepare_restart_to_windows()

        self.assertEqual(response, {"ok": True})

    async def test_reports_helper_failure_when_windows_is_not_verified(self):
        plugin = main.Plugin()
        with (
            patch.object(
                main,
                "detect_support",
                return_value=("/trusted/bin/boot-windows", None),
            ),
            patch.object(main, "windows_is_armed", return_value=(False, "not armed")),
            patch.object(
                main,
                "run_command",
                return_value=result(1, stderr="Cannot find Windows boot in EFI"),
            ),
        ):
            response = await plugin.prepare_restart_to_windows()

        self.assertFalse(response["ok"])
        self.assertIn("Cannot find Windows boot in EFI", response["error"])
        self.assertIn("not armed", response["error"])

    async def test_accepts_execution_error_when_windows_is_verified(self):
        plugin = main.Plugin()
        with (
            patch.object(
                main,
                "detect_support",
                return_value=("/trusted/bin/boot-windows", None),
            ),
            patch.object(
                main,
                "run_command",
                side_effect=subprocess.TimeoutExpired("boot-windows", 15),
            ),
            patch.object(main, "windows_is_armed", return_value=(True, None)),
        ):
            response = await plugin.prepare_restart_to_windows()

        self.assertEqual(response, {"ok": True})

    async def test_reports_execution_error_when_windows_is_not_verified(self):
        plugin = main.Plugin()
        with (
            patch.object(
                main,
                "detect_support",
                return_value=("/trusted/bin/boot-windows", None),
            ),
            patch.object(
                main,
                "run_command",
                side_effect=subprocess.TimeoutExpired("boot-windows", 15),
            ),
            patch.object(main, "windows_is_armed", return_value=(False, "not armed")),
        ):
            response = await plugin.prepare_restart_to_windows()

        self.assertFalse(response["ok"])
        self.assertIn("timed out", response["error"])
        self.assertIn("not armed", response["error"])


if __name__ == "__main__":
    unittest.main()
