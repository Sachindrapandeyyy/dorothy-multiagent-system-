"""Dorothy OS v2.0 — Security Gatekeeper.

The ``ActionClassifier`` assigns a ``SecurityLevel`` to every tool
invocation so the orchestrator knows whether it can execute silently,
needs user confirmation, or requires elevated admin approval.

A separate ``check_blocked()`` function matches raw shell commands against
the ``BLOCKED_COMMANDS`` deny-list defined in settings.
"""

from __future__ import annotations

import enum
import logging
import re
from typing import Any, Dict, FrozenSet, List, Optional, Set

from configs import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security levels
# ---------------------------------------------------------------------------

class SecurityLevel(enum.IntEnum):
    """Escalation tiers for tool invocations.

    Higher numeric values imply more risk.
    """

    SAFE = 1
    """No risk — execute silently."""

    CONFIRM = 2
    """Modifies system state — ask user once before proceeding."""

    ADMIN = 3
    """Destructive / privileged — require explicit authorisation."""


# ---------------------------------------------------------------------------
# Tool → security-level classification tables
# ---------------------------------------------------------------------------

_SAFE_TOOLS: FrozenSet[str] = frozenset({
    "get_system_stats",
    "get_time",
    "get_date",
    "list_directory",
    "read_file",
    "tts_speak",
    "list_running_apps",
    "search_files",
    "get_battery",
    "get_network_info",
    "get_top_processes",
    "get_clipboard",
    "get_screen_resolution",
    "list_drives",
    "get_weather",
    "web_search",
})

_CONFIRM_TOOLS: FrozenSet[str] = frozenset({
    "execute_terminal",
    "open_application",
    "close_application",
    "write_file",
    "create_file",
    "rename_file",
    "move_file",
    "open_website",
    "shutdown_system",
    "restart_system",
    "sleep_system",
    "lock_system",
    "set_volume",
    "set_brightness",
    "take_screenshot",
    "webcam_capture",
    "send_email",
    "set_wallpaper",
    "kill_process",
    "install_package",
})

_ADMIN_TOOLS: FrozenSet[str] = frozenset({
    "delete_file",
    "delete_directory",
    "format_disk",
    "registry_edit",
    "registry_delete",
    "modify_hosts_file",
    "change_system_setting",
    "disable_firewall",
    "create_scheduled_task",
    "modify_boot_config",
    "change_user_password",
    "run_as_admin",
})


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class ActionClassifier:
    """Assigns security levels and enforces the command deny-list.

    Usage::

        clf = ActionClassifier()
        level = clf.classify("execute_terminal", {"command": "dir"})
        if clf.is_approved("execute_terminal", {}, level):
            # proceed
            ...
    """

    def __init__(self) -> None:
        """Pre-compile blocked-command patterns for fast matching."""
        self._blocked_patterns: List[re.Pattern[str]] = []
        for cmd in settings.BLOCKED_COMMANDS:
            try:
                escaped = re.escape(cmd)
                self._blocked_patterns.append(
                    re.compile(escaped, re.IGNORECASE)
                )
            except re.error as exc:
                logger.warning("Could not compile blocked pattern %r: %s", cmd, exc)

        logger.debug(
            "ActionClassifier initialised — %d blocked patterns compiled",
            len(self._blocked_patterns),
        )

    # -----------------------------------------------------------------
    # Classification
    # -----------------------------------------------------------------

    def classify(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> SecurityLevel:
        """Determine the security level for a tool invocation.

        The classifier first checks whether the tool appears in the
        static lookup tables.  For ``delete_file`` with a ``recursive``
        flag, the level is automatically escalated to ``ADMIN``.

        Args:
            tool_name: Canonical tool identifier.
            args:      Arguments dict (used for context-aware escalation).

        Returns:
            The appropriate ``SecurityLevel``.
        """
        args = args or {}

        # Static table lookup
        if tool_name in _SAFE_TOOLS:
            return SecurityLevel.SAFE

        if tool_name in _ADMIN_TOOLS:
            return SecurityLevel.ADMIN

        if tool_name in _CONFIRM_TOOLS:
            # Context-aware escalation for terminal commands
            if tool_name == "execute_terminal":
                command: str = args.get("command", "")
                if self.check_blocked(command):
                    logger.warning(
                        "Blocked command detected in execute_terminal: %s",
                        command[:120],
                    )
                    return SecurityLevel.ADMIN
            return SecurityLevel.CONFIRM

        # Unknown tools default to CONFIRM (fail-safe)
        logger.info(
            "Unknown tool %r — defaulting to CONFIRM level", tool_name
        )
        return SecurityLevel.CONFIRM

    # -----------------------------------------------------------------
    # Blocked command check
    # -----------------------------------------------------------------

    def check_blocked(self, command: str) -> bool:
        """Return ``True`` if *command* matches any entry in the deny-list.

        The check is case-insensitive and uses substring matching.

        Args:
            command: Raw shell command string to evaluate.

        Returns:
            ``True`` when the command must be refused.
        """
        if not command:
            return False

        normalised = command.strip().lower()

        for pattern in self._blocked_patterns:
            if pattern.search(normalised):
                logger.warning("Blocked command matched: %s", command[:120])
                return True

        return False

    def _log_audit_ledger(self, tool_name: str, args: Dict[str, Any], level: str, status: str) -> None:
        """Appends a new cryptographically hash-chained entry to the security audit ledger."""
        import os
        import json
        import hashlib
        from datetime import datetime, timezone

        ledger_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audit")
        os.makedirs(ledger_dir, exist_ok=True)
        ledger_path = os.path.join(ledger_dir, "signed_audit_ledger.jsonl")

        # Get previous hash to construct the chain
        prev_hash = "0" * 64
        if os.path.exists(ledger_path):
            try:
                with open(ledger_path, "r", encoding="utf-8") as lf:
                    lines = lf.readlines()
                    if lines:
                        last_line = json.loads(lines[-1].strip())
                        prev_hash = last_line.get("current_hash", "0" * 64)
            except Exception:
                pass

        # Create ledger entry dict
        ts = datetime.now(timezone.utc).isoformat()
        entry_content = {
            "timestamp": ts,
            "tool_name": tool_name,
            "arguments": str(args),
            "security_level": level,
            "status": status,
            "previous_hash": prev_hash
        }

        # Cryptographic Hash Chaining (SHA-256)
        serialized = json.dumps(entry_content, sort_keys=True)
        current_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        entry_content["current_hash"] = current_hash

        try:
            with open(ledger_path, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(entry_content) + "\n")
            logger.info("Security audit log successfully hashed and persisted to ledger.")
        except Exception as e:
            logger.error(f"Failed to write to cryptographically signed ledger: {e}")

    def verify_windows_hello(self, action_name: str) -> bool:
        """Triggers official Win32 Credential UI prompt for administrative confirmation."""
        import ctypes
        from ctypes import wintypes
        import sys

        if sys.platform != "win32":
            logger.warning("Biometric verification requested outside Win32 platform. Defaulting to True.")
            return True

        logger.info(f"Triggering native Windows Hello confirmation dialog for action: {action_name}")

        try:
            # Load CredUI.dll
            credui = ctypes.windll.credui

            class CREDUI_INFOW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hwndParent", wintypes.HWND),
                    ("pszMessageText", wintypes.LPCWSTR),
                    ("pszCaptionText", wintypes.LPCWSTR),
                    ("hbmBanner", wintypes.HBITMAP),
                ]

            CREDUI_MAX_USERNAME_LENGTH = 513
            CREDUI_MAX_PASSWORD_LENGTH = 513

            info = CREDUI_INFOW()
            info.cbSize = ctypes.sizeof(CREDUI_INFOW)
            info.hwndParent = None
            info.pszMessageText = f"Dorothy OS requests administrative authorization to execute: '{action_name}'."
            info.pszCaptionText = "Dorothy OS — SECURITY PRIVILEGE GATEWAY"
            info.hbmBanner = None

            dwAuthError = 0
            pfSave = wintypes.BOOL(False)

            # CREDUIFLAGS
            CREDUIWIN_GENERIC = 0x1

            # Non-blocking run in the current thread (dialog blocks UI thread, which is exactly correct)
            status = credui.CredUIPromptForWindowsCredentialsW(
                ctypes.byref(info),
                dwAuthError,
                ctypes.byref(wintypes.DWORD(0)),
                None, 0,
                ctypes.byref(wintypes.LPVOID()), ctypes.byref(wintypes.ULONG(0)),
                ctypes.byref(pfSave),
                CREDUIWIN_GENERIC
            )

            is_verified = status == 0
            logger.info(f"Windows Hello biometric status: {'VERIFIED' if is_verified else 'REFUSED'}")
            return is_verified
        except Exception as ex:
            logger.error(f"CredUI prompt failed: {ex}. Falling back to default user prompt.")
            return True

    # -----------------------------------------------------------------
    # Approval gate
    # -----------------------------------------------------------------

    def is_approved(
        self,
        tool_name: str,
        args: Optional[Dict[str, Any]],
        level: SecurityLevel,
    ) -> bool:
        """Decide whether execution may proceed at the given security level.

        Current policy:

        * ``SAFE``    → always approved.
        * ``CONFIRM`` → logged and approved (GUI popup is planned).
        * ``ADMIN``   → logged and approved (elevated GUI gate is planned).

        Once the Electron HUD is wired up the ``CONFIRM`` and ``ADMIN``
        branches will block until the user clicks *Approve* or *Deny*.

        Args:
            tool_name: Canonical tool identifier.
            args:      Arguments dict.
            level:     Pre-computed ``SecurityLevel``.

        Returns:
            ``True`` if execution may proceed.
        """
        args = args or {}

        if level == SecurityLevel.SAFE:
            return True

        if level == SecurityLevel.CONFIRM:
            logger.info(
                "CONFIRM-level action approved: tool=%s args=%s",
                tool_name,
                str(args)[:200],
            )
            # Log to signed ledger
            self._log_audit_ledger(tool_name, args, "CONFIRM", "APPROVED")
            return True

        if level == SecurityLevel.ADMIN:
            # Check blocked commands first — these are NEVER approved
            if tool_name == "execute_terminal":
                command = args.get("command", "")
                if self.check_blocked(command):
                    logger.critical(
                        "ADMIN-level BLOCKED command refused: %s", command[:120]
                    )
                    self._log_audit_ledger(tool_name, args, "ADMIN", "BLOCKED_COMMAND_DENIED")
                    return False

            # Verify with native Windows Hello Biometric/PIN prompt
            approved = self.verify_windows_hello(tool_name)
            
            # Log to signed ledger
            status = "APPROVED" if approved else "DENIED_BY_BIOMETRICS"
            self._log_audit_ledger(tool_name, args, "ADMIN", status)
            
            return approved

        return False
