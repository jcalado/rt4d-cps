"""Theme management for RT-4D Editor.

Uses Qt's Fusion style which provides reliable light and dark palettes
across all platforms.
"""

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"

_SETTINGS_ORG = "RT4D-Editor"
_SETTINGS_APP = "RT4D-Editor"
_KEY_THEME = "theme"


def _is_dark_active() -> bool:
    """Check whether the currently applied palette is dark."""
    app = QApplication.instance()
    if app is None:
        return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _create_dark_palette() -> QPalette:
    """Create a dark color palette for the Fusion style."""
    p = QPalette()

    p.setColor(QPalette.ColorRole.Window, QColor(43, 43, 43))
    p.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
    p.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    p.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(128, 128, 128))
    p.setColor(QPalette.ColorRole.Button, QColor(58, 58, 58))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(60, 60, 60))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(224, 224, 224))
    p.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link, QColor(86, 156, 214))
    p.setColor(QPalette.ColorRole.LinkVisited, QColor(165, 130, 210))
    p.setColor(QPalette.ColorRole.Light, QColor(70, 70, 70))
    p.setColor(QPalette.ColorRole.Midlight, QColor(55, 55, 55))
    p.setColor(QPalette.ColorRole.Mid, QColor(45, 45, 45))
    p.setColor(QPalette.ColorRole.Dark, QColor(35, 35, 35))
    p.setColor(QPalette.ColorRole.Shadow, QColor(20, 20, 20))

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(128, 128, 128))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128, 128, 128))

    return p


def _create_light_palette() -> QPalette:
    """Create an explicit light color palette for the Fusion style.

    Fusion's ``standardPalette()`` inherits the OS dark-mode colors on
    Windows, so we define our own light palette instead.
    """
    p = QPalette()

    p.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 231, 227))
    p.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(128, 128, 128))
    p.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.Highlight, QColor(48, 140, 198))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
    p.setColor(QPalette.ColorRole.LinkVisited, QColor(255, 0, 255))
    p.setColor(QPalette.ColorRole.Light, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Midlight, QColor(202, 202, 202))
    p.setColor(QPalette.ColorRole.Mid, QColor(160, 160, 160))
    p.setColor(QPalette.ColorRole.Dark, QColor(120, 120, 120))
    p.setColor(QPalette.ColorRole.Shadow, QColor(80, 80, 80))

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(120, 120, 120))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(120, 120, 120))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(120, 120, 120))

    return p


def _get_system_is_dark() -> bool:
    """Detect whether the OS prefers a dark theme."""
    # Qt 6.5+ color scheme API
    try:
        from PySide6.QtGui import QGuiApplication
        scheme = QGuiApplication.styleHints().colorScheme()
        val = int(scheme)
        # 0 = Unknown, 1 = Light, 2 = Dark
        if val == 2:
            return True
        if val == 1:
            return False
        # Unknown — fall through to platform-specific detection
    except (AttributeError, TypeError):
        pass

    # Windows: read AppsUseLightTheme from the registry (0 = dark)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except (ImportError, OSError):
        pass

    return False


def _resolve_is_dark(mode: str) -> bool:
    """Resolve a theme mode string to a boolean (True = dark)."""
    if mode == THEME_DARK:
        return True
    if mode == THEME_LIGHT:
        return False
    return _get_system_is_dark()


# ── Public API ──────────────────────────────────────────────────


def get_saved_theme() -> str:
    """Return the persisted theme preference (defaults to 'system')."""
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    return s.value(_KEY_THEME, THEME_SYSTEM, type=str)


def save_theme(mode: str) -> None:
    """Persist the theme preference."""
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    s.setValue(_KEY_THEME, mode)


def apply_theme(app: QApplication, mode: str) -> None:
    """Apply the given theme mode to *app* immediately.

    Expects the Fusion style to already be set on *app* (done once at startup).
    """
    if _resolve_is_dark(mode):
        app.setPalette(_create_dark_palette())
    else:
        app.setPalette(_create_light_palette())


# ── Semantic colour helpers ─────────────────────────────────────


def hint_color() -> str:
    """Subdued text for descriptions and hints."""
    return "#999" if _is_dark_active() else "#666"


def warning_style() -> str:
    """Inline QSS for a warning info-box (background + text + border)."""
    if _is_dark_active():
        return (
            "QLabel { background-color: #4a3c00; color: #ffd866; "
            "border: 1px solid #7a6a20; padding: 10px; border-radius: 4px; }"
        )
    return (
        "QLabel { background-color: #fff3cd; color: #856404; "
        "border: 1px solid #ffc107; padding: 10px; border-radius: 4px; }"
    )


def error_color() -> str:
    """Colour for error / critical warnings."""
    return "#ff6b6b" if _is_dark_active() else "#cc0000"


def success_color() -> str:
    """Colour for positive / success messages."""
    return "#66cc66" if _is_dark_active() else "#008800"


def info_color() -> str:
    """Colour for neutral informational text."""
    return "#66aaff" if _is_dark_active() else "#0066cc"
