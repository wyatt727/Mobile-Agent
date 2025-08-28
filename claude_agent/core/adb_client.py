#!/usr/bin/env python3
"""
AdbClient - Handles all interactions with ADB for the NetHunter environment.
"""
import subprocess
import time
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)

class AdbClient:
    """
    Encapsulates ADB interactions for a NetHunter environment.
    All host-level actions must be performed via ADB.
    """
    def __init__(self, adb_path: str = "adb", retry_interval: int = 3):
        """
        Initializes the AdbClient.

        Args:
            adb_path: The path to the ADB executable. Defaults to "adb" (assumes it's in PATH).
            retry_interval: Time in seconds to wait before retrying ADB commands on authorization failure.
        """
        self.adb_path = adb_path
        self.retry_interval = retry_interval
        logger.info(f"AdbClient initialized with adb_path: {self.adb_path}")

    def _run_adb_command(self, command_args: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        """
        Runs an ADB command and captures its output.

        Args:
            command_args: A list of arguments for the ADB command (e.g., ["devices"])
            timeout: Timeout for the command execution.

        Returns:
            A tuple of (return_code, stdout, stderr).
        """
        full_command = [self.adb_path] + command_args
        logger.debug(f"Running ADB command: {' '.join(full_command)}")
        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            logger.debug(f"ADB command finished with return code: {result.returncode}")
            if result.returncode != 0:
                logger.warning(f"ADB command failed. Stderr: {result.stderr.strip()}")
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"ADB command timed out after {timeout} seconds: {' '.join(full_command)}")
            return -1, "", f"ADB command timed out after {timeout} seconds."
        except FileNotFoundError:
            logger.error(f"ADB executable not found at '{self.adb_path}'. Please ensure ADB is installed and in your PATH, or provide the correct path.")
            return -1, "", f"ADB executable not found at '{self.adb_path}'."
        except Exception as e:
            logger.error(f"Error running ADB command {' '.join(full_command)}: {e}")
            return -1, "", str(e)

    def wait_for_device_authorized(self, max_attempts: int = 30) -> bool:
        """
        Waits until an ADB device is authorized. Retries on "unauthorized" status.

        Args:
            max_attempts: Maximum number of attempts to wait for authorization.

        Returns:
            True if device is authorized, False otherwise.
        """
        logger.info("Waiting for ADB device authorization...")
        for attempt in range(1, max_attempts + 1):
            return_code, stdout, stderr = self._run_adb_command(["devices"])
            if return_code != 0:
                logger.error(f"Failed to list ADB devices. Stderr: {stderr}")
                time.sleep(self.retry_interval)
                continue

            if "unauthorized" in stdout:
                logger.warning(f"Device unauthorized. Retrying in {self.retry_interval} seconds (Attempt {attempt}/{max_attempts})...")
                time.sleep(self.retry_interval)
            elif "device" in stdout and "offline" not in stdout:
                logger.info("ADB device authorized.")
                return True
            else:
                logger.info(f"No authorized device found yet. Retrying in {self.retry_interval} seconds (Attempt {attempt}/{max_attempts})...")
                time.sleep(self.retry_interval)
        
        logger.error(f"Failed to get ADB device authorization after {max_attempts} attempts.")
        return False

    def shell(self, command: str, su: bool = False, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Executes a shell command on the connected Android device.

        Args:
            command: The shell command to execute.
            su: If True, execute the command with root privileges (su -c).
            timeout: Timeout for the command execution.

        Returns:
            A tuple of (return_code, stdout, stderr).
        """
        if su:
            full_command = f"su -c '{command.replace("'", "'\\''")}'" # Escape single quotes
        else:
            full_command = command
        
        logger.debug(f"Executing ADB shell command (su={su}): {full_command}")
        return self._run_adb_command(["shell", full_command], timeout=timeout)

    def push(self, local_path: str, remote_path: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Pushes a file from the local system (chroot) to the Android device.

        Args:
            local_path: The path to the file on the local system.
            remote_path: The destination path on the Android device.
            timeout: Timeout for the command execution.

        Returns:
            A tuple of (return_code, stdout, stderr).
        """
        logger.debug(f"Pushing file from {local_path} to {remote_path}")
        return self._run_adb_command(["push", local_path, remote_path], timeout=timeout)

    def pull(self, remote_path: str, local_path: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Pulls a file from the Android device to the local system (chroot).

        Args:
            remote_path: The path to the file on the Android device.
            local_path: The destination path on the local system.
            timeout: Timeout for the command execution.

        Returns:
            A tuple of (return_code, stdout, stderr).
        """
        logger.debug(f"Pulling file from {remote_path} to {local_path}")
        return self._run_adb_command(["pull", remote_path, local_path], timeout=timeout)

    def forward(self, local_port: int, remote_port: int, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Sets up port forwarding from the host to the device.

        Args:
            local_port: The local port on the chroot.
            remote_port: The remote port on the Android device.
            timeout: Timeout for the command execution.

        Returns:
            A tuple of (return_code, stdout, stderr).
        """
        logger.debug(f"Setting up ADB forward: tcp:{local_port} tcp:{remote_port}")
        return self._run_adb_command(["forward", f"tcp:{local_port}", f"tcp:{remote_port}"], timeout=timeout)

    def reverse(self, remote_port: int, local_port: int, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Sets up reverse port forwarding from the device to the host.

        Args:
            remote_port: The remote port on the Android device.
            local_port: The local port on the chroot.
            timeout: Timeout for the command execution.

        Returns:
            A tuple of (return_code, stdout, stderr).
        """
        logger.debug(f"Setting up ADB reverse: tcp:{remote_port} tcp:{local_port}")
        return self._run_adb_command(["reverse", f"tcp:{remote_port}", f"tcp:{local_port}"], timeout=timeout)

    def get_device_state(self, timeout: int = 10) -> str:
        """
        Gets the current state of the device (e.g., "device", "offline", "unauthorized").

        Returns:
            The device state string, or "unknown" if an error occurs.
        """
        return_code, stdout, stderr = self._run_adb_command(["get-state"], timeout=timeout)
        if return_code == 0:
            return stdout.strip()
        logger.warning(f"Failed to get device state. Stderr: {stderr}")
        return "unknown"

    def get_serialno(self, timeout: int = 10) -> Optional[str]:
        """
        Gets the serial number of the connected device.

        Returns:
            The serial number string, or None if not found or an error occurs.
        """
        return_code, stdout, stderr = self._run_adb_command(["get-serialno"], timeout=timeout)
        if return_code == 0 and stdout.strip():
            return stdout.strip()
        logger.warning(f"Failed to get device serial number. Stderr: {stderr}")
        return None
