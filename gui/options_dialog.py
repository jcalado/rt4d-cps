"""Application Options Dialog for RT-4D Editor"""

from typing import Tuple

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QCheckBox, QDoubleSpinBox, QPushButton, QGroupBox, QComboBox
)
from PySide6.QtCore import QSettings

from . import theme as _theme


class OptionsDialog(QDialog):
    """Dialog for configuring application options including repeater frequency shifts"""

    # QSettings configuration
    SETTINGS_ORG = "RT4D-Editor"
    SETTINGS_APP = "RT4D-Editor"

    # QSettings keys
    KEY_AUTO_SHIFT_ENABLED = "auto_shift_enabled"
    KEY_VHF_SHIFT = "vhf_shift_mhz"
    KEY_UHF_SHIFT = "uhf_shift_mhz"

    # Frequency ranges (MHz)
    VHF_MIN = 136.0
    VHF_MAX = 174.0
    UHF_MIN = 400.0
    UHF_MAX = 520.0

    # Default shift values (MHz)
    DEFAULT_VHF_SHIFT = 0.6
    DEFAULT_UHF_SHIFT = 5.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_settings()

    @staticmethod
    def _get_settings() -> QSettings:
        """Get application QSettings instance"""
        return QSettings(OptionsDialog.SETTINGS_ORG, OptionsDialog.SETTINGS_APP)

    def init_ui(self) -> None:
        """Initialize the dialog UI"""
        self.setWindowTitle("Options")
        self.setModal(True)
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Theme section
        theme_group = QGroupBox("Appearance")
        theme_layout = QFormLayout()

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["System", "Light", "Dark"])
        self.combo_theme.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addRow("Theme:", self.combo_theme)

        theme_group.setLayout(theme_layout)
        main_layout.addWidget(theme_group)

        # Repeater Frequency Shift section
        shift_group = QGroupBox("Repeater Frequency Shift")
        shift_layout = QVBoxLayout()

        # Enable checkbox
        self.chk_auto_shift = QCheckBox("Enable automatic TX frequency shift for new channels")
        shift_layout.addWidget(self.chk_auto_shift)

        # Description using constants
        desc_label = QLabel(
            "When enabled, new channels will automatically have their TX frequency\n"
            "calculated based on the RX frequency and the configured shift values.\n"
            f"VHF range: {self.VHF_MIN:.0f}-{self.VHF_MAX:.0f} MHz, "
            f"UHF range: {self.UHF_MIN:.0f}-{self.UHF_MAX:.0f} MHz"
        )
        desc_label.setStyleSheet(f"color: {_theme.hint_color()}; font-size: 11px;")
        shift_layout.addWidget(desc_label)

        # Shift values form
        form_layout = QFormLayout()

        self.spin_vhf_shift = QDoubleSpinBox()
        self.spin_vhf_shift.setRange(-50.0, 50.0)
        self.spin_vhf_shift.setDecimals(3)
        self.spin_vhf_shift.setSuffix(" MHz")
        self.spin_vhf_shift.setSingleStep(0.1)
        form_layout.addRow(
            f"VHF Shift ({self.VHF_MIN:.0f}-{self.VHF_MAX:.0f} MHz):",
            self.spin_vhf_shift
        )

        self.spin_uhf_shift = QDoubleSpinBox()
        self.spin_uhf_shift.setRange(-50.0, 50.0)
        self.spin_uhf_shift.setDecimals(3)
        self.spin_uhf_shift.setSuffix(" MHz")
        self.spin_uhf_shift.setSingleStep(0.5)
        form_layout.addRow(
            f"UHF Shift ({self.UHF_MIN:.0f}-{self.UHF_MAX:.0f} MHz):",
            self.spin_uhf_shift
        )

        shift_layout.addLayout(form_layout)

        # Hint about shift direction
        hint_label = QLabel(
            "Tip: Use positive values for repeater output above input,\n"
            "negative values for repeater output below input."
        )
        hint_label.setStyleSheet(f"color: {_theme.hint_color()}; font-size: 10px; font-style: italic;")
        shift_layout.addWidget(hint_label)

        shift_group.setLayout(shift_layout)
        main_layout.addWidget(shift_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept)
        button_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(button_layout)

    _THEME_LABELS = {"system": "System", "light": "Light", "dark": "Dark"}
    _THEME_MODES = {"System": "system", "Light": "light", "Dark": "dark"}

    def load_settings(self) -> None:
        """Load settings from QSettings"""
        settings = self._get_settings()

        self.chk_auto_shift.setChecked(
            settings.value(self.KEY_AUTO_SHIFT_ENABLED, False, type=bool)
        )
        self.spin_vhf_shift.setValue(
            settings.value(self.KEY_VHF_SHIFT, self.DEFAULT_VHF_SHIFT, type=float)
        )
        self.spin_uhf_shift.setValue(
            settings.value(self.KEY_UHF_SHIFT, self.DEFAULT_UHF_SHIFT, type=float)
        )

        saved = _theme.get_saved_theme()
        self.combo_theme.setCurrentText(self._THEME_LABELS.get(saved, "System"))

    def save_settings(self) -> None:
        """Save settings to QSettings"""
        settings = self._get_settings()

        settings.setValue(self.KEY_AUTO_SHIFT_ENABLED, self.chk_auto_shift.isChecked())
        settings.setValue(self.KEY_VHF_SHIFT, self.spin_vhf_shift.value())
        settings.setValue(self.KEY_UHF_SHIFT, self.spin_uhf_shift.value())

    def accept(self) -> None:
        """Handle OK button - save settings and close"""
        self.save_settings()
        super().accept()

    def _on_theme_changed(self, text: str) -> None:
        """Apply the selected theme immediately."""
        mode = self._THEME_MODES.get(text, "system")
        _theme.save_theme(mode)
        _theme.apply_theme(QApplication.instance(), mode)

    @staticmethod
    def get_auto_shift_settings() -> Tuple[bool, float, float]:
        """
        Retrieve auto-shift settings from QSettings.

        Returns:
            Tuple of (enabled, vhf_shift_mhz, uhf_shift_mhz)
        """
        settings = OptionsDialog._get_settings()
        enabled = settings.value(
            OptionsDialog.KEY_AUTO_SHIFT_ENABLED, False, type=bool
        )
        vhf_shift = settings.value(
            OptionsDialog.KEY_VHF_SHIFT, OptionsDialog.DEFAULT_VHF_SHIFT, type=float
        )
        uhf_shift = settings.value(
            OptionsDialog.KEY_UHF_SHIFT, OptionsDialog.DEFAULT_UHF_SHIFT, type=float
        )
        return enabled, vhf_shift, uhf_shift

    @staticmethod
    def calculate_tx_freq(rx_freq_mhz: float) -> float:
        """
        Calculate TX frequency based on RX frequency and configured shifts.

        If auto-shift is disabled or RX is outside VHF/UHF ranges,
        returns the same frequency as RX.

        Args:
            rx_freq_mhz: RX frequency in MHz

        Returns:
            TX frequency in MHz
        """
        enabled, vhf_shift, uhf_shift = OptionsDialog.get_auto_shift_settings()

        if not enabled:
            return rx_freq_mhz

        # VHF range
        if OptionsDialog.VHF_MIN <= rx_freq_mhz <= OptionsDialog.VHF_MAX:
            return rx_freq_mhz + vhf_shift

        # UHF range
        if OptionsDialog.UHF_MIN <= rx_freq_mhz <= OptionsDialog.UHF_MAX:
            return rx_freq_mhz + uhf_shift

        # Outside VHF/UHF ranges - no shift
        return rx_freq_mhz
