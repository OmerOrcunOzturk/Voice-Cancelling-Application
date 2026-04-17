from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import numpy as np

from filtre_app.audio.devices import (
    find_selected_device,
    pick_supported_audio_config,
    pick_default_output,
    query_input_output_devices,
)
from filtre_app.audio.processor import AudioProcessor
from filtre_app.config import (
    APP_TITLE,
    DEFAULT_GATE_THRESHOLD_DB,
    DEFAULT_INPUT_GAIN,
    DEFAULT_MONITORING,
    DEFAULT_NOISE_REDUCTION,
    DEFAULT_OUTPUT_VOLUME,
    MIN_WINDOW_SIZE,
    WINDOW_SIZE,
)


class SliderRow(QWidget):
    def __init__(self, label, min_value, max_value, value, formatter, on_change, parent=None):
        super().__init__(parent)
        self.min_value = min_value
        self.max_value = max_value
        self.formatter = formatter
        self.on_change = on_change

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)

        self.label = QLabel(label)
        self.label.setObjectName("rowLabel")
        layout.addWidget(self.label, 0, 0)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(self._handle_change)
        layout.addWidget(self.slider, 0, 1)

        self.value_label = QLabel()
        self.value_label.setObjectName("valueBadge")
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setFixedWidth(72)
        layout.addWidget(self.value_label, 0, 2)

        layout.setColumnStretch(1, 1)
        self.set_value(value)

    def _slider_to_value(self, slider_value):
        ratio = slider_value / 1000.0
        return self.min_value + (self.max_value - self.min_value) * ratio

    def _value_to_slider(self, value):
        ratio = (value - self.min_value) / (self.max_value - self.min_value)
        return int(round(max(0.0, min(1.0, ratio)) * 1000))

    def _handle_change(self, slider_value):
        value = self._slider_to_value(slider_value)
        self.value_label.setText(self.formatter(value))
        self.on_change(value)

    def get_value(self):
        return self._slider_to_value(self.slider.value())

    def set_value(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(self._value_to_slider(value))
        self.slider.blockSignals(False)
        self.value_label.setText(self.formatter(value))

    def set_enabled(self, enabled):
        self.slider.setEnabled(enabled)


class InfoCard(QFrame):
    def __init__(self, title, subtitle=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        self.layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("cardSubtitle")
            subtitle_label.setWordWrap(True)
            self.layout.addWidget(subtitle_label)


class MicrophoneFilterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)

        width, height = map(int, WINDOW_SIZE.split("x"))
        self.resize(width, height)
        self.setMinimumSize(*MIN_WINDOW_SIZE)

        self.processor = AudioProcessor()
        self.running = False
        self.input_devices = []
        self.output_devices = []
        self.dark_mode = True

        self._build_ui()
        self._apply_theme()
        self._refresh_devices(initial=True)
        self._sync_controls()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(60)
        self.refresh_timer.timeout.connect(self._refresh_meter)
        self.refresh_timer.start()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(24, 22, 24, 22)
        root_layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        eyebrow = QLabel("REAL-TIME VOICE CHAIN")
        eyebrow.setObjectName("eyebrow")
        top_row.addWidget(eyebrow)
        top_row.addStretch(1)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeToggle")
        self.theme_button.setCheckable(True)
        self.theme_button.clicked.connect(self._toggle_theme)
        top_row.addWidget(self.theme_button)
        hero_layout.addLayout(top_row)

        title = QLabel("Canli mikrofon filtresini daha temiz bir kontrol masasi ile yonet.")
        title.setObjectName("heroTitle")
        title.setWordWrap(True)
        hero_layout.addWidget(title)

        subtitle = QLabel(
            "Giris cihazini sec, filtre gucunu ayarla ve temizlenmis sesi gorusme "
            "uygulamalarina hazir hale getir."
        )
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(subtitle)

        badges = QHBoxLayout()
        badges.setSpacing(10)
        badges.addWidget(self._build_badge("Canli gosterge"))
        badges.addWidget(self._build_badge("VB-Cable hazir"))
        badges.addWidget(self._build_badge("Tek tikla baslat"))
        badges.addStretch(1)
        hero_layout.addLayout(badges)
        root_layout.addWidget(hero)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        root_layout.addLayout(content_layout, 1)

        left_column = QVBoxLayout()
        left_column.setSpacing(18)
        content_layout.addLayout(left_column, 3)

        right_column = QVBoxLayout()
        right_column.setSpacing(18)
        content_layout.addLayout(right_column, 2)

        device_card = InfoCard(
            "Ses Aygitlari",
            "Toplanti uygulamalari icin temiz sesi sanal cihaza gonderebilir, "
            "normal kullanim icin fiziksel cikisa donebilirsin.",
        )
        left_column.addWidget(device_card)
        self._build_device_section(device_card.layout)

        controls_card = InfoCard(
            "Filtre Kontrolleri",
            "Gain, noise reduction ve gate seviyelerini anlik olarak degistir. "
            "Ayarlar ses motoruna hemen uygulanir.",
        )
        left_column.addWidget(controls_card)
        self._build_controls_section(controls_card.layout)

        meter_card = InfoCard(
            "Canli Seviye",
            "Konusurken seviye cubugu hareket eder. Buradan zincirin aktif olup "
            "olmadigini hizlica gorebilirsin.",
        )
        right_column.addWidget(meter_card)
        self._build_meter_section(meter_card.layout)

        action_card = InfoCard(
            "Oturum",
            "Filtreyi baslatinca secili mikrofon girisi temizlenir ve cikis aygitina verilir.",
        )
        right_column.addWidget(action_card)
        self._build_action_section(action_card.layout)

        right_column.addStretch(1)

    def _build_badge(self, text):
        badge = QLabel(text)
        badge.setObjectName("badge")
        return badge

    def _build_device_section(self, layout):
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        input_label = QLabel("Giris Mikrofonu")
        input_label.setObjectName("fieldLabel")
        grid.addWidget(input_label, 0, 0)

        self.input_combo = QComboBox()
        self.input_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.input_combo, 0, 1)

        output_label = QLabel("Filtrelenmis Ses Cikisi")
        output_label.setObjectName("fieldLabel")
        grid.addWidget(output_label, 1, 0)

        self.output_combo = QComboBox()
        self.output_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.output_combo, 1, 1)

        self.refresh_button = QPushButton("Aygitlari Yenile")
        self.refresh_button.clicked.connect(self._refresh_devices)
        grid.addWidget(self.refresh_button, 0, 2, 2, 1)

        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        help_text = QLabel(
            "Gorusme uygulamalarinda filtreli ses kullanmak icin cikis olarak "
            "'CABLE Input' veya benzeri sanal aygiti sec."
        )
        help_text.setObjectName("hintText")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

    def _build_controls_section(self, layout):
        self.input_gain_row = SliderRow(
            "Ses Alma Duzeyi",
            0.5,
            4.0,
            DEFAULT_INPUT_GAIN,
            lambda value: f"{value:.2f}",
            lambda _value: self._sync_controls(),
        )
        layout.addWidget(self.input_gain_row)

        self.output_volume_row = SliderRow(
            "Monitor Ses Cikisi",
            0.0,
            1.0,
            DEFAULT_OUTPUT_VOLUME,
            lambda value: f"{value:.2f}",
            lambda _value: self._sync_controls(),
        )
        layout.addWidget(self.output_volume_row)

        self.noise_reduction_row = SliderRow(
            "Gurultu Engelleyici",
            0.0,
            100.0,
            DEFAULT_NOISE_REDUCTION,
            lambda value: f"{value:.0f}%",
            lambda _value: self._sync_controls(),
        )
        layout.addWidget(self.noise_reduction_row)

        self.gate_row = SliderRow(
            "Noise Gate Esigi",
            -70.0,
            -20.0,
            DEFAULT_GATE_THRESHOLD_DB,
            lambda value: f"{value:.0f} dB",
            lambda _value: self._sync_controls(),
        )
        layout.addWidget(self.gate_row)

        self.monitor_checkbox = QCheckBox("Hoparlore geri ver (monitoring)")
        self.monitor_checkbox.setChecked(DEFAULT_MONITORING)
        self.monitor_checkbox.toggled.connect(self._toggle_monitoring)
        layout.addWidget(self.monitor_checkbox)

    def _build_meter_section(self, layout):
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(18)
        layout.addWidget(self.level_bar)

        self.level_value = QLabel("Seviye: -inf dB")
        self.level_value.setObjectName("meterValue")
        layout.addWidget(self.level_value)

        self.route_value = QLabel("Hazir")
        self.route_value.setObjectName("routeValue")
        self.route_value.setWordWrap(True)
        layout.addWidget(self.route_value)

    def _build_action_section(self, layout):
        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.start_button = QPushButton("Baslat")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start)
        button_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Durdur")
        self.stop_button.clicked.connect(self._stop)
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.stop_button)
        layout.addLayout(button_row)

        self.status_label = QLabel("Hazir")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        note = QLabel(
            "Not: Sanal kablo kullanirsan temizlenmis sesi Discord, Zoom veya "
            "benzeri uygulamalara mikrofon gibi verebilirsin."
        )
        note.setObjectName("hintText")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _apply_theme(self):
        self.setFont(QFont("Segoe UI", 11))
        self.theme_button.blockSignals(True)
        self.theme_button.setChecked(self.dark_mode)
        self.theme_button.setText("Dark mode acik" if self.dark_mode else "Light mode acik")
        self.theme_button.blockSignals(False)
        self.setStyleSheet(self._dark_stylesheet() if self.dark_mode else self._light_stylesheet())

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _light_stylesheet(self):
        return """
            QMainWindow {
                background: #f3f0e8;
            }
            #hero {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #203a2f,
                    stop:0.55 #2b5742,
                    stop:1 #3f7a5d
                );
                border-radius: 24px;
            }
            #eyebrow {
                color: rgba(241, 242, 228, 0.76);
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            #heroTitle {
                color: #f8f4ea;
                font-size: 34px;
                font-weight: 700;
            }
            #heroSubtitle {
                color: rgba(248, 244, 234, 0.82);
                font-size: 15px;
            }
            #badge {
                background: rgba(248, 244, 234, 0.14);
                color: #f6f0de;
                border: 1px solid rgba(248, 244, 234, 0.18);
                border-radius: 15px;
                padding: 7px 12px;
                font-weight: 600;
            }
            #themeToggle {
                background: rgba(248, 244, 234, 0.14);
                border: 1px solid rgba(248, 244, 234, 0.20);
                color: #f8f4ea;
                min-height: 36px;
                border-radius: 12px;
                padding: 0 14px;
            }
            #themeToggle:hover {
                background: rgba(248, 244, 234, 0.22);
            }
            #card {
                background: #fbf8f1;
                border: 1px solid #ddd6c8;
                border-radius: 20px;
            }
            #cardTitle {
                color: #1c2b22;
                font-size: 18px;
                font-weight: 700;
            }
            #cardSubtitle {
                color: #667065;
                font-size: 13px;
            }
            #fieldLabel, #rowLabel {
                color: #27392f;
                font-weight: 600;
            }
            QComboBox, QPushButton {
                min-height: 46px;
                border-radius: 12px;
                padding: 0 12px;
                font-size: 14px;
            }
            QComboBox {
                background: #f5efe3;
                border: 1px solid #d6cab6;
                color: #1d2a22;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox:disabled {
                color: #7b7b72;
            }
            QPushButton {
                background: #e9dfcf;
                border: 1px solid #d3c2ad;
                color: #213127;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #efe5d5;
            }
            QPushButton:pressed {
                background: #dbcdb9;
            }
            QPushButton:disabled {
                background: #ede7dc;
                color: #8a8a83;
            }
            #primaryButton {
                background: #18362a;
                border: 1px solid #18362a;
                color: #f8f4ea;
            }
            #primaryButton:hover {
                background: #224836;
            }
            #valueBadge {
                background: #efe6d9;
                color: #304337;
                border-radius: 12px;
                padding: 8px 10px;
                font-weight: 700;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #ddd2c0;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #2f6b50;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #f8f4ea;
                border: 2px solid #2f6b50;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QCheckBox {
                color: #23342a;
                spacing: 10px;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 1px solid #b6ad9f;
                background: #f5efe3;
            }
            QCheckBox::indicator:checked {
                background: #2f6b50;
                border-color: #2f6b50;
            }
            QProgressBar {
                background: #e5dbca;
                border: none;
                border-radius: 9px;
            }
            QProgressBar::chunk {
                border-radius: 9px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2a5e48,
                    stop:1 #61a980
                );
            }
            #meterValue {
                color: #182b21;
                font-size: 30px;
                font-weight: 700;
            }
            #routeValue {
                color: #5b655a;
                font-size: 13px;
                line-height: 1.4;
            }
            #statusLabel {
                color: #1d2e24;
                font-size: 16px;
                font-weight: 600;
            }
            #hintText {
                color: #667065;
                font-size: 13px;
            }
        """

    def _dark_stylesheet(self):
        return """
            QMainWindow {
                background: #101713;
            }
            #hero {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #10261d,
                    stop:0.58 #173529,
                    stop:1 #234a38
                );
                border-radius: 24px;
                border: 1px solid #284436;
            }
            #eyebrow {
                color: rgba(214, 237, 221, 0.72);
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            #heroTitle {
                color: #f3f7ef;
                font-size: 34px;
                font-weight: 700;
            }
            #heroSubtitle {
                color: rgba(234, 244, 235, 0.76);
                font-size: 15px;
            }
            #badge {
                background: rgba(243, 247, 239, 0.10);
                color: #e9f5ea;
                border: 1px solid rgba(243, 247, 239, 0.12);
                border-radius: 15px;
                padding: 7px 12px;
                font-weight: 600;
            }
            #themeToggle {
                background: rgba(243, 247, 239, 0.10);
                border: 1px solid rgba(243, 247, 239, 0.14);
                color: #eef7ee;
                min-height: 36px;
                border-radius: 12px;
                padding: 0 14px;
            }
            #themeToggle:hover {
                background: rgba(243, 247, 239, 0.18);
            }
            #card {
                background: #171f1b;
                border: 1px solid #26302b;
                border-radius: 20px;
            }
            #cardTitle {
                color: #eef7ee;
                font-size: 18px;
                font-weight: 700;
            }
            #cardSubtitle {
                color: #97a79d;
                font-size: 13px;
            }
            #fieldLabel, #rowLabel {
                color: #d8e3da;
                font-weight: 600;
            }
            QComboBox, QPushButton {
                min-height: 46px;
                border-radius: 12px;
                padding: 0 12px;
                font-size: 14px;
            }
            QComboBox {
                background: #202923;
                border: 1px solid #2e3a33;
                color: #edf5ee;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox:disabled {
                color: #77837b;
            }
            QPushButton {
                background: #222d26;
                border: 1px solid #334038;
                color: #edf5ee;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2a372f;
            }
            QPushButton:pressed {
                background: #324138;
            }
            QPushButton:disabled {
                background: #1a221d;
                color: #68746d;
            }
            #primaryButton {
                background: #5ec18d;
                border: 1px solid #5ec18d;
                color: #102117;
            }
            #primaryButton:hover {
                background: #74d79f;
            }
            #valueBadge {
                background: #202a24;
                color: #bce1c6;
                border-radius: 12px;
                padding: 8px 10px;
                font-weight: 700;
                border: 1px solid #2e3932;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #243029;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #66c695;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #f3f7ef;
                border: 2px solid #66c695;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QCheckBox {
                color: #d9e6dc;
                spacing: 10px;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 1px solid #435148;
                background: #202923;
            }
            QCheckBox::indicator:checked {
                background: #66c695;
                border-color: #66c695;
            }
            QProgressBar {
                background: #223028;
                border: none;
                border-radius: 9px;
            }
            QProgressBar::chunk {
                border-radius: 9px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b8d63,
                    stop:1 #7be0a9
                );
            }
            #meterValue {
                color: #f0f7f1;
                font-size: 30px;
                font-weight: 700;
            }
            #routeValue {
                color: #93a39a;
                font-size: 13px;
                line-height: 1.4;
            }
            #statusLabel {
                color: #e4efe6;
                font-size: 16px;
                font-weight: 600;
            }
            #hintText {
                color: #97a79d;
                font-size: 13px;
            }
        """

    def _sync_controls(self):
        self.processor.set_controls(
            input_gain=self.input_gain_row.get_value(),
            output_volume=self.output_volume_row.get_value(),
            noise_reduction=self.noise_reduction_row.get_value() / 100.0,
            gate_threshold_db=self.gate_row.get_value(),
        )

    def _refresh_devices(self, initial=False):
        try:
            input_devices, output_devices = query_input_output_devices()
        except Exception as exc:
            self.status_label.setText(f"Aygitlar okunamadi: {exc}")
            return

        previous_input = self.input_combo.currentText()
        previous_output = self.output_combo.currentText()

        self.input_devices = input_devices
        self.output_devices = output_devices

        input_labels = [label for label, _, _ in input_devices]
        output_labels = [label for label, _, _ in output_devices]

        self.input_combo.blockSignals(True)
        self.output_combo.blockSignals(True)
        self.input_combo.clear()
        self.output_combo.clear()
        self.input_combo.addItems(input_labels)
        self.output_combo.addItems(output_labels)
        self.input_combo.blockSignals(False)
        self.output_combo.blockSignals(False)

        if input_labels:
            selected_input = previous_input if previous_input in input_labels else input_labels[0]
            self.input_combo.setCurrentText(selected_input)

        if output_labels:
            selected_output = (
                previous_output if previous_output in output_labels else pick_default_output(output_devices)
            )
            self.output_combo.setCurrentText(selected_output)

        if not initial:
            self.status_label.setText("Ses aygitlari yenilendi")

    def _toggle_monitoring(self, enabled):
        self.processor.set_monitoring(enabled)

    def _start(self):
        if self.running:
            return

        input_device, input_info = find_selected_device(
            self.input_devices, self.input_combo.currentText()
        )
        output_device, output_info = find_selected_device(
            self.output_devices, self.output_combo.currentText()
        )

        if input_device is None or output_device is None:
            QMessageBox.critical(
                self,
                "Ses Aygiti Hatasi",
                "Gecerli bir giris ve cikis aygiti secilmeden akisi baslatamam.",
            )
            return

        sample_rate, output_channels = pick_supported_audio_config(
            input_device=input_device,
            input_info=input_info,
            output_device=output_device,
            output_info=output_info,
        )

        try:
            self.processor.start(
                input_device=input_device,
                output_device=output_device,
                sample_rate=sample_rate,
                output_channels=output_channels,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Ses Aygiti Hatasi", str(exc))
            self.status_label.setText(str(exc))
            return

        self.running = True
        route = f"{self.input_combo.currentText()} -> {self.output_combo.currentText()}"
        self.status_label.setText(f"Filtre aktif: {route}")
        self.route_value.setText(f"Aktif rota: {route}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.input_combo.setEnabled(False)
        self.output_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)

    def _stop(self):
        if not self.running:
            return

        self.processor.stop()
        self.running = False
        self.status_label.setText("Dinleme durduruldu")
        self.route_value.setText("Hazir")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.input_combo.setEnabled(True)
        self.output_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.level_bar.setValue(0)
        self.level_value.setText("Seviye: -inf dB")

    def _refresh_meter(self):
        level, peak, status = self.processor.get_meter_state()
        self.level_bar.setValue(int(max(level, peak) * 100))

        if level <= 1e-6:
            self.level_value.setText("Seviye: -inf dB")
        else:
            level_db = 20 * np.log10(level / 3.0 + 1e-12)
            self.level_value.setText(f"Seviye: {level_db:5.1f} dB")

        messages = self.processor.drain_status_messages()
        if messages:
            self.status_label.setText(messages[-1])
        elif not self.running:
            self.status_label.setText(status)

    def closeEvent(self, event: QCloseEvent):
        if self.running:
            self.processor.stop()
        event.accept()
