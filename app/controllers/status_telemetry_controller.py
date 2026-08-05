"""Status bar telemetry controller for Echo Pro windows."""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QProgressBar

from audio_device import device_manager


class StatusTelemetryController:
    """Builds and refreshes status-bar telemetry widgets for a window."""

    def __init__(self, window) -> None:
        self.window = window

    def setup_status_bar_widgets(self) -> None:
        status = self.window.status
        status.setSizeGripEnabled(False)
        status.setFixedHeight(24)
        status.setStyleSheet(
            "QStatusBar { border-top: 1px solid #0f2a44; }"
            "QStatusBar::item { border: none; }"
        )

        self.window.status_cpu_bar = QProgressBar(self.window)
        self.window.status_cpu_bar.setRange(0, 100)
        self.window.status_cpu_bar.setValue(0)
        self.window.status_cpu_bar.setTextVisible(False)
        self.window.status_cpu_bar.setFixedSize(56, 12)

        self.window.status_cpu_label = QLabel("CPU 0%")
        self.window.status_cpu_label.setMinimumWidth(58)
        self.window.status_ram_label = QLabel("RAM 0%")
        self.window.status_ram_label.setMinimumWidth(64)
        self.window.status_driver_label = QLabel("Driver: --")
        self.window.status_driver_label.setMinimumWidth(120)
        self.window.status_sample_rate_label = QLabel("SR 44.1k")
        self.window.status_sample_rate_label.setMinimumWidth(60)
        self.window.status_buffer_label = QLabel("BUF 256")
        self.window.status_buffer_label.setMinimumWidth(54)
        self.window.status_latency_label = QLabel("0.0 ms")
        self.window.status_latency_label.setMinimumWidth(58)
        self.window.status_latency_label.setStyleSheet("color: #00F0FF; font-family: Consolas, monospace;")
        self.window.status_mode_label = QLabel("State: Idle")
        self.window.status_mode_label.setMinimumWidth(140)
        self.window.status_mode_label.setStyleSheet("color: #8fc7ff;")
        self.window.status_project_label = QLabel("Project: Untitled")
        self.window.status_project_label.setMinimumWidth(130)
        self.window.status_project_label.setStyleSheet("color: #cfd4db;")
        self.window.status_save_dot = QLabel("●")
        self.window.status_save_dot.setMinimumWidth(10)
        self.window.status_save_dot.setStyleSheet("color: #e6a23c;")
        self.window.status_save_text = QLabel("Unsaved")
        self.window.status_save_text.setMinimumWidth(58)

        status.addPermanentWidget(self.window.status_cpu_bar)
        status.addPermanentWidget(self.window.status_cpu_label)
        status.addPermanentWidget(self.window.status_ram_label)
        status.addPermanentWidget(self.window.status_driver_label)
        status.addPermanentWidget(self.window.status_sample_rate_label)
        status.addPermanentWidget(self.window.status_buffer_label)
        status.addPermanentWidget(self.window.status_latency_label)
        status.addPermanentWidget(self.window.status_mode_label)
        status.addPermanentWidget(self.window.status_project_label, 1)
        status.addPermanentWidget(self.window.status_save_dot)
        status.addPermanentWidget(self.window.status_save_text)

        self.window.status_telemetry_timer = QTimer(self.window)
        self.window.status_telemetry_timer.setInterval(1000)
        self.window.status_telemetry_timer.timeout.connect(self.window._refresh_status_bar_telemetry)
        self.window.status_telemetry_timer.start()
        self.refresh_status_bar_telemetry()

    def read_system_usage_percent(self) -> Tuple[Optional[float], Optional[float]]:
        try:
            import psutil  # type: ignore

            return float(psutil.cpu_percent(interval=None)), float(psutil.virtual_memory().percent)
        except Exception:
            return None, None

    def refresh_status_bar_telemetry(self) -> None:
        cpu_percent, ram_percent = self.read_system_usage_percent()
        if cpu_percent is None:
            self.window.status_cpu_bar.setValue(0)
            self.window.status_cpu_label.setText("CPU --")
        else:
            cpu_clamped = max(0, min(100, int(round(cpu_percent))))
            self.window.status_cpu_bar.setValue(cpu_clamped)
            self.window.status_cpu_label.setText(f"CPU {cpu_clamped}%")

        if ram_percent is None:
            self.window.status_ram_label.setText("RAM --")
        else:
            ram_clamped = max(0, min(100, int(round(ram_percent))))
            self.window.status_ram_label.setText(f"RAM {ram_clamped}%")

        selected_output_id = self.window.selected_output_device_id
        if selected_output_id is None:
            selected_output_id = device_manager.selected_output_device
        output_device = device_manager.get_device(int(selected_output_id)) if selected_output_id is not None else None
        driver_label = "--"
        if output_device is not None:
            driver_label = str(output_device.api)
        self.window.status_driver_label.setText(f"Driver: {driver_label}")

        sample_rate = int(device_manager.selected_sample_rate)
        if hasattr(self.window, "sample_rate_combo") and getattr(self.window.sample_rate_combo, "count", None) is not None:
            selected_sample_rate = self.window.sample_rate_combo.currentData()
            if isinstance(selected_sample_rate, int) and selected_sample_rate > 0:
                sample_rate = selected_sample_rate
        self.window.status_sample_rate_label.setText(f"SR {sample_rate / 1000.0:.1f}k")

        buffer_size = int(device_manager.selected_buffer_size)
        self.window.status_buffer_label.setText(f"BUF {buffer_size}")

        latency_ms = float(device_manager.get_total_latency())
        self.window.status_latency_label.setText(f"{latency_ms:.1f} ms")

        project_name = str(self.window.current_project.name or "Untitled")
        self.window.status_project_label.setText(f"Project: {project_name}")

        dirty = self.window._is_project_dirty()
        if dirty:
            self.window.status_save_dot.setStyleSheet("color: #e6a23c;")
            self.window.status_save_text.setText("Unsaved")
            self.window.status_save_text.setStyleSheet("color: #e6a23c;")
        else:
            self.window.status_save_dot.setStyleSheet("color: #26d07c;")
            self.window.status_save_text.setText("Saved")
            self.window.status_save_text.setStyleSheet("color: #26d07c;")

        self.window._refresh_mastering_chain_page()
