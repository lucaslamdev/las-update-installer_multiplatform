"""VmOptions model for VM options file management.

Matches Java behavior:
- save order: currentDir, serverPort, extrasVmOptions, parameterArgs
- -include-options uses space separator, not equals
- load uses String.contains (line.contains(key)) for matching
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional


SERVER_PORT_KEY = "-Dserver.port"
INCLUDE_VMOPTIONS_KEY = "-include-options"
CURRENT_DIR_KEY = "-Dmv-update.dir"


@dataclass
class VmOptions:
    """Represents VM options configuration for a module."""
    server_port: int = -1
    parameter_args: list[str] = field(default_factory=list)
    extras_vm_options: list[str] = field(default_factory=list)
    current_dir: Optional[str] = None

    def save_to_file(self, file_path: str):
        """Write VM options to a file.

        Java write order: currentDir, serverPort, extrasVmOptions, parameterArgs.
        -include-options uses space separator (not equals).
        serverPort condition: != -1 (includes port 0).
        """
        lines = []
        # 1. currentDir
        if self.current_dir:
            lines.append(f"{CURRENT_DIR_KEY}={self.current_dir}")
        # 2. serverPort (condition: != -1, so port 0 is included)
        if self.server_port != -1:
            lines.append(f"{SERVER_PORT_KEY}={self.server_port}")
        # 3. extrasVmOptions (space separator, not equals)
        for extra in self.extras_vm_options:
            lines.append(f"{INCLUDE_VMOPTIONS_KEY} {extra}")
        # 4. parameterArgs
        for arg in self.parameter_args:
            lines.append(arg)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            if lines:
                f.write("\n")

    @classmethod
    def load_from_file(cls, file_path: str) -> VmOptions:
        """Read VM options from a file.

        Java uses String.contains(key) for matching (matches anywhere in line).
        -include-options: removes key from line and trims.
        """
        if not os.path.exists(file_path):
            return cls()

        opts = cls()
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Java uses contains() not startswith()
                if SERVER_PORT_KEY in line:
                    try:
                        opts.server_port = int(line.split("=", 1)[1])
                    except (ValueError, IndexError):
                        pass
                elif INCLUDE_VMOPTIONS_KEY in line:
                    # Java: line.replace(key, "").trim()
                    value = line.replace(INCLUDE_VMOPTIONS_KEY, "").strip()
                    if value.startswith("="):
                        value = value[1:].strip()
                    if value:
                        opts.extras_vm_options.append(value)
                elif CURRENT_DIR_KEY in line:
                    try:
                        opts.current_dir = line.split("=", 1)[1]
                    except IndexError:
                        pass
                else:
                    opts.parameter_args.append(line)
        return opts
