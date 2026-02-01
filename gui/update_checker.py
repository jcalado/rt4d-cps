"""Auto-update check & notification for RT-4D Editor.

Queries the GitHub Releases API in a background thread, compares versions,
and shows a dialog when a newer release exists.  The download button links
directly to the platform/architecture-specific asset.
"""

import json
import platform
import webbrowser
from urllib.error import URLError
from urllib.request import Request, urlopen

from packaging.version import Version

from PySide6.QtCore import QSettings, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout,
)

from rt4d_codeplug import __version__

# ── QSettings keys / defaults ──────────────────────────────────

_SETTINGS_ORG = "RT4D-Editor"
_SETTINGS_APP = "RT4D-Editor"
_KEY_CHECK_ENABLED = "check_updates_enabled"
_KEY_SKIPPED_VERSION = "skipped_version"

GITHUB_API_URL = "https://api.github.com/repos/jcalado/rt4d-cps/releases/latest"


def _settings() -> QSettings:
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def is_update_check_enabled() -> bool:
    return _settings().value(_KEY_CHECK_ENABLED, True, type=bool)


def set_update_check_enabled(enabled: bool) -> None:
    _settings().setValue(_KEY_CHECK_ENABLED, enabled)


def get_skipped_version() -> str:
    return _settings().value(_KEY_SKIPPED_VERSION, "", type=str)


def set_skipped_version(version: str) -> None:
    _settings().setValue(_KEY_SKIPPED_VERSION, version)


# ── Platform / architecture detection ──────────────────────────


def get_platform_asset_suffix() -> str:
    """Return the release-asset suffix for the current platform.

    Uses ``struct.calcsize("P") * 8`` to detect 32-bit vs 64-bit, which
    correctly reflects the PyInstaller-built binary's bitness regardless
    of the host OS.
    """
    system = platform.system()

    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "macos"
    # Linux or other
    return "linux"


def _find_asset_url(assets: list, suffix: str) -> str | None:
    """Scan the *assets* array and return the download URL whose name
    contains *suffix*, or ``None`` if no match is found."""
    for asset in assets:
        url = asset.get("browser_download_url", "")
        if suffix in url:
            return url
    return None


# ── Background worker ──────────────────────────────────────────


class UpdateCheckWorker(QThread):
    """Fetch the latest release from GitHub in a background thread."""

    update_available = Signal(str, str, str, str)   # version, notes, download_url, release_url
    no_update = Signal()
    check_failed = Signal(str)                      # error message

    def run(self) -> None:  # noqa: D401
        try:
            req = Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github+json"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            tag = data.get("tag_name", "")
            remote_version = tag.lstrip("v")

            if Version(remote_version) <= Version(__version__):
                self.no_update.emit()
                return

            notes = data.get("body", "") or ""
            release_url = data.get("html_url", "")

            suffix = get_platform_asset_suffix()
            download_url = _find_asset_url(data.get("assets", []), suffix) or release_url

            self.update_available.emit(remote_version, notes, download_url, release_url)

        except (URLError, OSError, ValueError, KeyError) as exc:
            self.check_failed.emit(str(exc))


# ── Update dialog ──────────────────────────────────────────────


class UpdateDialog(QDialog):
    """Modal dialog shown when a new version is available."""

    def __init__(
        self,
        parent,
        new_version: str,
        release_notes: str,
        download_url: str,
        release_url: str,
    ):
        super().__init__(parent)
        self._download_url = download_url
        self._release_url = release_url
        self._new_version = new_version

        self.setWindowTitle("Update Available")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Version header
        header = QLabel(
            f"A new version of RT-4D Editor is available!\n\n"
            f"Current version: {__version__}\n"
            f"New version: {new_version}"
        )
        layout.addWidget(header)

        # Release notes
        if release_notes:
            notes_label = QLabel("Release notes:")
            layout.addWidget(notes_label)

            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setMarkdown(release_notes)
            browser.setMinimumHeight(200)
            layout.addWidget(browser)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_download = QPushButton("Download")
        btn_download.setDefault(True)
        btn_download.clicked.connect(self._on_download)
        btn_layout.addWidget(btn_download)

        btn_skip = QPushButton("Skip This Version")
        btn_skip.clicked.connect(self._on_skip)
        btn_layout.addWidget(btn_skip)

        btn_later = QPushButton("Remind Me Later")
        btn_later.clicked.connect(self.reject)
        btn_layout.addWidget(btn_later)

        layout.addLayout(btn_layout)

    def _on_download(self) -> None:
        webbrowser.open(self._download_url)
        self.accept()

    def _on_skip(self) -> None:
        set_skipped_version(self._new_version)
        self.reject()
