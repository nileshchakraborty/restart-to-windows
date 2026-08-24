import os
import re
import shutil
import subprocess
from collections.abc import Sequence

try:
    import decky
except ModuleNotFoundError:  # Decky is not present in the unit-test environment.
    decky = None


COMMAND_TIMEOUT_SECONDS = 15
SETUP_COMMAND = "ujust setup-boot-windows-steam"
WINDOWS_BOOT_ENTRY = re.compile(
    r"^Boot([0-9A-Fa-f]{4})\*?\s+Windows Boot Manager(?:\t.*)?\s*$"
)
BOOT_NEXT = re.compile(r"^BootNext:\s+([0-9A-Fa-f]{4})\s*$")


def system_command_path() -> str:
    """Return the platform's trusted default executable search path."""
    return os.confstr("CS_PATH") or os.defpath


def find_boot_windows() -> str | None:
    """Find Bazzite's installed helper without searching user-writable paths."""
    return shutil.which("boot-windows", path=system_command_path())


def find_system_command(name: str) -> str | None:
    return shutil.which(name, path=system_command_path())


def parse_windows_boot_targets(output: str) -> set[str]:
    targets = set()
    for line in output.splitlines():
        match = WINDOWS_BOOT_ENTRY.match(line)
        if match:
            targets.add(match.group(1).upper())
    return targets


def parse_boot_next(output: str) -> str | None:
    for line in output.splitlines():
        match = BOOT_NEXT.match(line)
        if match:
            return match.group(1).upper()
    return None


def run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )


def command_error(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    detail = result.stderr.strip() or result.stdout.strip()
    return f"{fallback}: {detail}" if detail else fallback


def windows_is_armed() -> tuple[bool, str | None]:
    efibootmgr = find_system_command("efibootmgr")
    if efibootmgr is None:
        return False, "efibootmgr is unavailable for verification"

    try:
        state = run_command([efibootmgr])
    except (OSError, subprocess.SubprocessError) as command_failure:
        return False, f"Unable to inspect the one-time boot target: {command_failure}"

    if state.returncode != 0:
        return False, command_error(state, "Unable to inspect the one-time boot target")

    windows_targets = parse_windows_boot_targets(state.stdout)
    boot_next = parse_boot_next(state.stdout)
    if boot_next is None or boot_next not in windows_targets:
        return False, "Windows is not the verified one-time boot target"
    return True, None


def detect_support() -> tuple[str | None, str | None]:
    helper = find_boot_windows()
    if helper is None:
        return (
            None,
            "Restart to Windows is not configured. Run "
            f"`{SETUP_COMMAND}` in Bazzite first.",
        )
    return helper, None


def log(message: str) -> None:
    if decky is not None:
        decky.logger.debug(message)


class Plugin:
    async def _main(self) -> None:
        pass

    async def _unload(self) -> None:
        pass

    async def get_restart_support(self) -> dict[str, bool | str]:
        helper, error = detect_support()
        if helper is None:
            return {"available": False, "error": error or "Unknown error"}
        return {"available": True}

    async def prepare_restart_to_windows(self) -> dict[str, bool | str]:
        log("Restart confirmation reached the backend")

        # Re-check immediately before execution so a stale UI cannot invoke a
        # helper that was removed after the plugin loaded.
        helper, error = detect_support()
        if helper is None:
            log("Restart request stopped: Bazzite helper is unavailable")
            return {"ok": False, "error": error or "Unknown error"}

        log("Delegating the one-time Windows boot to Bazzite")
        helper_failure: str | None = None
        try:
            restart = run_command([helper])
        except (OSError, subprocess.SubprocessError) as command_failure:
            log("Bazzite helper raised an error")
            helper_failure = f"Bazzite's boot-windows helper failed: {command_failure}"
            restart = None

        # The Bazzite helper also calls `reboot`, but that command is not usable
        # from Decky's backend context. Treat its exit status only as diagnostic:
        # success is determined by reading back the one-time EFI target.
        armed, verification_error = windows_is_armed()
        if armed:
            log("Windows target verified; Steam may now request the restart")
            return {"ok": True}

        log("Bazzite helper did not leave Windows armed")
        helper_error = helper_failure or command_error(
            restart, "Bazzite's boot-windows helper failed"
        )
        return {
            "ok": False,
            "error": helper_error
            + (f"; {verification_error}" if verification_error else ""),
        }
