"""VS Code integration for AIDB.

This module provides integration with VS Code and its forks (Cursor, Windsurf, VSCodium)
to enable execution of tasks and launch configurations through the AIDB VS Code Bridge
extension.
"""

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from importlib import resources
from pathlib import Path
from typing import Any

from aidb.common import AidbContext
from aidb.common.constants import (
    COMMAND_CHECK_TIMEOUT_S,
    DEFAULT_VSCODE_BRIDGE_PORT,
    EXTENSION_INSTALL_TIMEOUT_S,
    EXTENSION_LIST_TIMEOUT_S,
)
from aidb.common.errors import ConfigurationError, DebugConnectionError
from aidb.patterns.base import Obj
from aidb_common.env import reader


class IDEType(Enum):
    """Supported VS Code variants."""

    VSCODE = "vscode"
    CURSOR = "cursor"
    WINDSURF = "windsurf"
    VSCODIUM = "vscodium"
    CODE_OSS = "code-oss"
    UNKNOWN = "unknown"


@dataclass
class IDEInfo:
    """Information about detected IDE."""

    type: IDEType
    cli_command: str
    name: str
    version: str | None = None
    extensions_dir: Path | None = None


class IDEDetector:
    """Detect installed VS Code variants."""

    IDE_COMMANDS = {
        IDEType.VSCODE: ["code"],
        IDEType.CURSOR: ["cursor"],
        IDEType.WINDSURF: ["windsurf"],
        IDEType.VSCODIUM: ["codium", "vscodium"],
        IDEType.CODE_OSS: ["code-oss"],
    }

    IDE_ENV_VARS = {
        "VSCODE_IPC_HOOK": IDEType.VSCODE,
        "CURSOR_IPC_HOOK": IDEType.CURSOR,
        "WINDSURF_IPC_HOOK": IDEType.WINDSURF,
        "VSCODIUM_IPC_HOOK": IDEType.VSCODIUM,
    }

    @classmethod
    async def detect(cls) -> IDEInfo | None:
        """Detect the installed VS Code variant.

        Returns
        -------
        IDEInfo, optional
            Information about detected IDE, or None if not found
        """
        for var, ide_type in cls.IDE_ENV_VARS.items():
            if reader.read_str(var, default=None):
                cli_commands = cls.IDE_COMMANDS.get(ide_type, [])
                if cli_commands:
                    for cmd in cli_commands:
                        if await cls._check_command(cmd):
                            return await cls._create_ide_info(ide_type, cmd)

        for ide_type, commands in cls.IDE_COMMANDS.items():
            for cmd in commands:
                if await cls._check_command(cmd):
                    return await cls._create_ide_info(ide_type, cmd)

        return None

    @classmethod
    async def _create_ide_info(cls, ide_type: IDEType, cmd: str) -> IDEInfo:
        """Create IDEInfo instance with common data.

        Parameters
        ----------
        ide_type : IDEType
            The IDE type
        cmd : str
            The CLI command

        Returns
        -------
        IDEInfo
            Configured IDE information
        """
        return IDEInfo(
            type=ide_type,
            cli_command=cmd,
            name=ide_type.value.title(),
            version=await cls._get_version(cmd),
            extensions_dir=cls._get_extensions_dir(ide_type),
        )

    @staticmethod
    async def _check_command(command: str) -> bool:
        """Check if a command exists in PATH.

        Parameters
        ----------
        command : str
            Command name to check

        Returns
        -------
        bool
            True if command is available
        """
        try:
            process = await asyncio.create_subprocess_exec(
                command,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(
                process.communicate(),
                timeout=COMMAND_CHECK_TIMEOUT_S,
            )
            return True
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            return False

    @staticmethod
    async def _get_version(command: str) -> str | None:
        """Get IDE version from CLI command.

        Parameters
        ----------
        command : str
            Command to get version from

        Returns
        -------
        str, optional
            Version string if available
        """
        try:
            process = await asyncio.create_subprocess_exec(
                command,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=COMMAND_CHECK_TIMEOUT_S,
            )
            if process.returncode == 0:
                # Parse version from output (first line usually contains version)
                stdout_text = stdout.decode() if stdout else ""
                lines = stdout_text.strip().split("\n")
                if lines:
                    return lines[0]
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            pass
        return None

    @classmethod
    async def detect_available_ides(cls) -> list[IDEType]:
        """Detect all available VS Code variants on the system.

        Returns
        -------
        List[IDEType]
            List of detected IDE types
        """
        available = []
        for ide_type, commands in cls.IDE_COMMANDS.items():
            for command in commands:
                if await cls._check_command(command):
                    available.append(ide_type)
                    break  # Found this IDE type, no need to check other commands
        return available

    @classmethod
    async def detect_current_ide(cls) -> IDEType:
        """Detect the currently running VS Code variant.

        Returns
        -------
        IDEType
            Type of detected IDE, or IDEType.UNKNOWN if not detected
        """
        ide_info = await cls.detect()
        return ide_info.type if ide_info else IDEType.UNKNOWN

    @classmethod
    async def get_ide_command(cls, ide_type: IDEType) -> str | None:
        """Get the CLI command for an IDE type.

        Parameters
        ----------
        ide_type : IDEType
            The IDE type to get command for

        Returns
        -------
        str, optional
            CLI command if available
        """
        commands = cls.IDE_COMMANDS.get(ide_type, [])
        for command in commands:
            if await cls._check_command(command):
                return command
        return commands[0] if commands else None

    @staticmethod
    def _get_extensions_dir(ide_type: IDEType) -> Path | None:
        """Get the extensions directory for the IDE."""
        home = Path.home()

        # Map IDE types to their typical extension directories
        dirs = {
            IDEType.VSCODE: home / ".vscode" / "extensions",
            IDEType.CURSOR: home / ".cursor" / "extensions",
            IDEType.WINDSURF: home / ".windsurf" / "extensions",
            IDEType.VSCODIUM: home / ".vscode-oss" / "extensions",
            IDEType.CODE_OSS: home / ".vscode-oss" / "extensions",
        }

        ext_dir = dirs.get(ide_type)
        if ext_dir and ext_dir.exists():
            return ext_dir

        return None


class VSCodeIntegration(Obj):
    """Integration with VS Code for task execution."""

    EXTENSION_ID = "aidb.aidb-vscode-bridge"
    BRIDGE_PORT = DEFAULT_VSCODE_BRIDGE_PORT

    def __init__(
        self,
        ide_type: IDEType | None = None,
        ctx: AidbContext | None = None,
    ):
        """Initialize VS Code integration.

        Parameters
        ----------
        ide_type : IDEType, optional
            Specific IDE type to use. If None, will auto-detect.
        ctx : AidbContext, optional
            Application context for logging
        """
        super().__init__(ctx)
        self.ide_info: IDEInfo | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._connected = False

        # If IDE type specified, store it for later detection
        self._requested_ide_type = ide_type if ide_type != IDEType.UNKNOWN else None

    async def initialize(self) -> bool:
        """Initialize the VSCode integration by detecting IDE.

        Returns
        -------
        bool
            True if IDE was detected successfully
        """
        self.ctx.debug("Initializing VSCode integration")
        if self._requested_ide_type:
            self.ctx.debug(f"Detecting specific IDE type: {self._requested_ide_type}")
            return await self._detect_specific_ide(self._requested_ide_type)
        self.ctx.debug("Auto-detecting IDE")
        return await self.detect_ide()

    async def _detect_specific_ide(self, ide_type: IDEType) -> bool:
        """Detect a specific IDE type.

        Parameters
        ----------
        ide_type : IDEType
            The specific IDE type to detect

        Returns
        -------
        bool
            True if IDE detected
        """
        command = await IDEDetector.get_ide_command(ide_type)
        if command:
            self.ide_info = IDEInfo(
                type=ide_type,
                cli_command=command,
                name=ide_type.value,
                version=await IDEDetector._get_version(command),
                extensions_dir=IDEDetector._get_extensions_dir(ide_type),
            )
            self.ctx.info(f"Using {self.ide_info.name} ({self.ide_info.cli_command})")
            return True
        self.ctx.warning(f"{ide_type.value} not found")
        return False

    async def detect_ide(self) -> bool:
        """Detect installed VS Code variant.

        Returns
        -------
        bool
            True if IDE detected, False otherwise
        """
        self.ide_info = await IDEDetector.detect()
        if self.ide_info:
            self.ctx.info(
                f"Detected {self.ide_info.name} ({self.ide_info.cli_command})",
            )
            if self.ide_info.version:
                self.ctx.debug(f"Version: {self.ide_info.version}")
            return True
        self.ctx.warning("No VS Code variant detected")
        return False

    async def is_extension_installed(self) -> bool:
        """Check if AIDB bridge extension is installed.

        Returns
        -------
        bool
            True if extension is installed
        """
        if not self.ide_info:
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                self.ide_info.cli_command,
                "--list-extensions",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=EXTENSION_LIST_TIMEOUT_S,
            )
            if process.returncode == 0:
                stdout_text = stdout.decode() if stdout else ""
                installed = self.EXTENSION_ID in stdout_text
                if installed:
                    self.ctx.debug("AIDB bridge extension is installed")
                return installed
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            pass

        return False

    async def install_extension(
        self,
        vsix_path: Path | None = None,
        use_marketplace: bool = False,
    ) -> bool:
        """Install the AIDB bridge extension.

        Parameters
        ----------
        vsix_path : Path, optional
            Path to the VSIX file. If None, uses bundled extension.
            Ignored if use_marketplace is True.
        use_marketplace : bool
            If True, install from VS Code marketplace instead of local VSIX.

        Returns
        -------
        bool
            True if installation successful
        """
        if not self.ide_info:
            msg = "No IDE detected for extension installation"
            raise ConfigurationError(msg)

        try:
            if use_marketplace:
                # Install from marketplace using extension ID
                self.ctx.info(
                    f"Installing AIDB bridge extension "
                    f"from marketplace: {self.EXTENSION_ID}",
                )
                process = await asyncio.create_subprocess_exec(
                    self.ide_info.cli_command,
                    "--install-extension",
                    self.EXTENSION_ID,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=EXTENSION_INSTALL_TIMEOUT_S,
                )
                result_stdout = stdout.decode() if stdout else ""
                result_stderr = stderr.decode() if stderr else ""
            else:
                # Install from local VSIX file
                if vsix_path is None:
                    vsix_path = self._get_bundled_vsix_path()

                if not vsix_path or not vsix_path.exists():
                    msg = f"VSIX file not found: {vsix_path}"
                    raise ConfigurationError(msg)

                self.ctx.info(f"Installing AIDB bridge extension from {vsix_path}")
                process = await asyncio.create_subprocess_exec(
                    self.ide_info.cli_command,
                    "--install-extension",
                    str(vsix_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=EXTENSION_INSTALL_TIMEOUT_S,
                )
                result_stdout = stdout.decode() if stdout else ""
                result_stderr = stderr.decode() if stderr else ""

            if process.returncode == 0:
                self.ctx.info("AIDB bridge extension installed successfully")
                return True
            error_msg = result_stderr or result_stdout
            if use_marketplace and "not found" in error_msg.lower():
                self.ctx.error(
                    f"Extension not found in marketplace. Error: {error_msg}",
                )
                self.ctx.info(
                    "Note: Marketplace installation requires internet connection "
                    "and the extension to be published.",
                )
            else:
                self.ctx.error(f"Failed to install extension: {error_msg}")
            return False
        except asyncio.TimeoutError:
            self.ctx.error("Extension installation timed out")
            return False
        except FileNotFoundError:
            self.ctx.error(f"IDE command not found: {self.ide_info.cli_command}")
            return False
        except Exception as e:
            self.ctx.error(f"Unexpected error during extension installation: {e}")
            return False

    def _get_bundled_vsix_path(self) -> Path | None:
        """Get path to bundled VSIX file.

        Uses importlib.resources for resource access and checks development
        directory structure as fallback.

        Returns
        -------
        Path, optional
            Path to VSIX file if found
        """
        vsix_filename = "aidb-vscode-bridge.vsix"

        # Use importlib.resources (project requires Python 3.10+)
        try:
            import aidb.resources

            files = resources.files(aidb.resources)
            vsix_resource = files.joinpath(vsix_filename)

            if vsix_resource.is_file():
                with resources.as_file(vsix_resource) as vsix_path:
                    from aidb.common.context import AidbContext

                    ctx = AidbContext()
                    temp_dir = Path(ctx.get_storage_path("vscode_bridge"))
                    temp_vsix = temp_dir / vsix_filename
                    temp_vsix.write_bytes(vsix_path.read_bytes())
                    return temp_vsix
        except (ImportError, FileNotFoundError, AttributeError) as e:
            self.ctx.debug(f"importlib.resources failed: {e}")

        # Final fallback: check extensions directory in development repo
        # This is useful during development before packaging
        repo_root = Path(__file__).parent.parent.parent

        # Try multiple possible locations
        possible_paths = [
            repo_root / "extensions" / "aidb-vscode-bridge" / vsix_filename,
            repo_root / "resources" / vsix_filename,
            repo_root / "src" / "aidb" / "resources" / vsix_filename,
        ]

        for vsix_path in possible_paths:
            if vsix_path.exists():
                self.ctx.debug(f"Found VSIX in development directory: {vsix_path}")
                return vsix_path

        self.ctx.debug("VSIX file not found in any location")
        return None

    async def connect(self, timeout: float = 5.0) -> bool:
        """Connect to the VS Code bridge extension.

        Parameters
        ----------
        timeout : float
            Connection timeout in seconds

        Returns
        -------
        bool
            True if connected successfully
        """
        if self._connected:
            return True

        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", self.BRIDGE_PORT),
                timeout=timeout,
            )
            self._connected = True
            self.ctx.debug(f"Connected to VS Code bridge on port {self.BRIDGE_PORT}")
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
            self.ctx.debug(f"Failed to connect to VS Code bridge: {e}")
            self.reader = None
            self.writer = None
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from the VS Code bridge extension."""
        if self.writer:
            try:
                self.ctx.debug("Disconnecting from VS Code bridge")
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                self.ctx.debug(f"Error during disconnect: {e}")
            finally:
                self.writer = None
                self.reader = None
                self._connected = False

    async def _send_command(self, command: str, **kwargs) -> dict[str, Any]:
        """Send a command to the VS Code bridge.

        Parameters
        ----------
        command : str
            Command to execute
        **kwargs
            Additional command parameters

        Returns
        -------
        dict
            Response from the bridge

        Raises
        ------
        AidbError
            If not connected or command fails
        """
        if not self._connected:
            msg = "Not connected to VS Code bridge"
            raise DebugConnectionError(msg)

        if not self.writer or not self.reader:
            msg = "Stream not initialized"
            raise DebugConnectionError(msg)

        request = {"command": command, **kwargs}
        request_json = json.dumps(request) + "\n"

        try:
            # Send request
            self.writer.write(request_json.encode())
            await self.writer.drain()

            # Read response (until newline)
            response_data = await self.reader.readuntil(b"\n")
            return json.loads(response_data.decode().strip())
        except Exception as e:
            msg = f"Failed to communicate with VS Code bridge: {e}"
            raise DebugConnectionError(msg) from e

    async def execute_task(self, task_name: str | None = None) -> dict[str, Any]:
        """Execute a VS Code task.

        Parameters
        ----------
        task_name : str, optional
            Name of the task to execute. If None, shows task picker.

        Returns
        -------
        dict
            Execution result
        """
        return await self._send_command("executeTask", taskName=task_name)

    async def get_task_list(self) -> list[dict[str, Any]]:
        """Get list of available tasks.

        Returns
        -------
        list
            List of available tasks
        """
        response = await self._send_command("getTaskList")
        if response.get("success"):
            return response.get("tasks", [])
        msg = f"Failed to get task list: {response.get('error')}"
        raise DebugConnectionError(
            msg,
        )

    async def execute_launch_config(
        self,
        config_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute a launch configuration.

        Parameters
        ----------
        config_name : str, optional
            Name of the configuration. If None, shows picker.

        Returns
        -------
        dict
            Execution result
        """
        return await self._send_command("executeLaunchConfig", configName=config_name)

    async def ping(self) -> bool:
        """Ping the VS Code bridge to check connectivity.

        Returns
        -------
        bool
            True if bridge responds
        """
        try:
            response = await self._send_command("ping")
            return response.get("message") == "pong"
        except Exception:
            return False


def prompt_extension_install(ctx: AidbContext) -> bool:
    """Prompt user to install VS Code bridge extension.

    Parameters
    ----------
    ctx : AidbContext
        Application context

    Returns
    -------
    bool
        True if user wants to install
    """
    ctx.info(
        "The AIDB VS Code Bridge extension is required for task execution support.\n"
        "\n"
        "To install:\n"
        "1. The extension will be automatically installed when you proceed\n"
        "2. VS Code will need to be restarted after installation\n"
        "3. The bridge will enable preLaunchTask and postDebugTask execution\n"
        "\n"
        "Would you like to install the extension now?",
    )
    return True
