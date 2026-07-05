from __future__ import annotations

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
)
from PyQt5.QtCore import QTime

from app.core.location import campus_names, locations_for_campus


class SettingsDialog(QDialog):
    def __init__(self, settings: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.settings = settings or {}
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.campus_combo = QComboBox()
        self.campus_combo.addItems(campus_names())
        self.campus_combo.currentTextChanged.connect(self._refresh_locations)
        form.addRow("校区", self.campus_combo)

        self.location_mode_combo = QComboBox()
        self.location_mode_combo.addItems(["默认地点", "固定地点", "随机偏移地点"])
        form.addRow("地点模式", self.location_mode_combo)

        self.fixed_location_combo = QComboBox()
        form.addRow("固定地点", self.fixed_location_combo)

        self.save_session_checkbox = QCheckBox("保存 Session")
        form.addRow("", self.save_session_checkbox)

        self.debug_checkbox = QCheckBox("开启调试日志")
        form.addRow("", self.debug_checkbox)

        self.auto_checkin_checkbox = QCheckBox("启用定时自动打卡")
        form.addRow("", self.auto_checkin_checkbox)

        self.auto_checkin_time_edit = QTimeEdit()
        self.auto_checkin_time_edit.setDisplayFormat("HH:mm")
        form.addRow("自动打卡时间", self.auto_checkin_time_edit)

        self.auto_checkin_scope_combo = QComboBox()
        self.auto_checkin_scope_combo.addItems(["全部账号", "当前账号"])
        form.addRow("自动打卡范围", self.auto_checkin_scope_combo)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 60)
        self.timeout_spin.setSuffix(" 秒")
        form.addRow("请求超时", self.timeout_spin)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "campus": self.campus_combo.currentText(),
            "location_mode": self.location_mode_combo.currentText(),
            "fixed_location_index": self.fixed_location_combo.currentIndex(),
            "save_session": self.save_session_checkbox.isChecked(),
            "debug": self.debug_checkbox.isChecked(),
            "auto_checkin_enabled": self.auto_checkin_checkbox.isChecked(),
            "auto_checkin_time": self.auto_checkin_time_edit.time().toString("HH:mm"),
            "auto_checkin_scope": self.auto_checkin_scope_combo.currentText(),
            "timeout": self.timeout_spin.value(),
        }

    def _load(self) -> None:
        campus = self.settings.get("campus") or "宜宾"
        idx = self.campus_combo.findText(campus)
        self.campus_combo.setCurrentIndex(max(0, idx))
        self._refresh_locations()
        mode_idx = self.location_mode_combo.findText(self.settings.get("location_mode") or "默认地点")
        self.location_mode_combo.setCurrentIndex(max(0, mode_idx))
        self.fixed_location_combo.setCurrentIndex(int(self.settings.get("fixed_location_index") or 0))
        self.save_session_checkbox.setChecked(bool(self.settings.get("save_session", True)))
        self.debug_checkbox.setChecked(bool(self.settings.get("debug", False)))
        self.auto_checkin_checkbox.setChecked(bool(self.settings.get("auto_checkin_enabled", False)))
        auto_time = QTime.fromString(str(self.settings.get("auto_checkin_time") or "19:31"), "HH:mm")
        self.auto_checkin_time_edit.setTime(auto_time if auto_time.isValid() else QTime(19, 31))
        scope_idx = self.auto_checkin_scope_combo.findText(self.settings.get("auto_checkin_scope") or "全部账号")
        self.auto_checkin_scope_combo.setCurrentIndex(max(0, scope_idx))
        self.timeout_spin.setValue(int(self.settings.get("timeout") or 15))

    def _refresh_locations(self) -> None:
        self.fixed_location_combo.clear()
        for location in locations_for_campus(self.campus_combo.currentText()):
            self.fixed_location_combo.addItem(location.address)
