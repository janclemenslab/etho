import logging
import sys
import threading
from typing import Optional

from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QSizePolicy

from .app import MainWindow as EthoMainWindow
from .app import _system_icon
from .resumable import ResumableExperimentRunner


logger = logging.getLogger(__name__)
CONTROL_COLUMN_WIDTH = 145


class WorkerSignals(QObject):
    finished = Signal(str)


class MainWindow(EthoMainWindow):
    def __init__(self, protocol_folder: Optional[str] = None, playlist_folder: Optional[str] = None):
        super().__init__(protocol_folder, playlist_folder)
        self.setWindowTitle("etho resumable control")
        self.runner = None
        self.worker = None
        self.progress_thread = None
        self.progress_stop_event = None
        self.run_active = False
        self.signals = WorkerSignals()
        self.signals.finished.connect(self.on_worker_finished)
        try:
            self.run_timer.timeout.disconnect(self.sync_run_state)
        except (TypeError, RuntimeError):
            pass
        self.run_timer.stop()

        buttons = self.layout.itemAtPosition(0, 0).layout()
        self.button["Initialize hardware"] = QPushButton("Initialize hardware")
        self.button["Initialize hardware"].clicked.connect(self.initialize_hardware)
        self.button["Shutdown hardware"] = QPushButton("Shutdown hardware")
        self.button["Shutdown hardware"].clicked.connect(self.shutdown_hardware)
        self.status_label = QLabel("Select a protocol and initialize hardware.")
        self.status_label.setWordWrap(True)
        self.status_label.setFixedWidth(CONTROL_COLUMN_WIDTH)
        self.status_label.setMinimumHeight(72)
        self.status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        buttons.insertWidget(1, self.button["Initialize hardware"])
        buttons.insertWidget(2, self.button["Shutdown hardware"])
        buttons.insertSpacing(3, 12)
        buttons.insertSpacing(6, 8)
        buttons.insertWidget(buttons.count() - 1, self.status_label)
        self.layout.setColumnMinimumWidth(0, CONTROL_COLUMN_WIDTH)
        self.layout.setColumnStretch(0, 0)
        for button in self.button.values():
            if hasattr(button, "setFixedWidth"):
                button.setFixedWidth(CONTROL_COLUMN_WIDTH)
        self.set_resumable_buttons("idle")

    def refresh_lists(self, init: bool = False):
        super().refresh_lists(init)
        if self.playlists_view.selected_string is None:
            self.playlists_view.selected_string = str(self.playlists_view.model()._data.iloc[0, 0])
        if self.protocols_view.selected_string is None:
            self.protocols_view.selected_string = str(self.protocols_view.model()._data.iloc[0, 0])

    def selected_playlist(self):
        if self.playlists_view.selected_string is None:
            return None
        return (self.playlist_folder / self.playlists_view.selected_string).as_posix()

    def run_background(self, message, target):
        if self.worker is not None and self.worker.is_alive():
            return
        self.status_label.setText(message)
        self.set_resumable_buttons("busy")

        def wrapped():
            try:
                status = target()
            except Exception as e:
                logger.exception("Resumable GUI action failed.")
                self.run_active = False
                status = f"Error: {e}"
            self.signals.finished.emit(status)

        self.worker = threading.Thread(target=wrapped, daemon=True)
        self.worker.start()

    def on_worker_finished(self, status):
        self.worker = None
        self.status_label.setText(status)
        if not self.run_active:
            self.run_timer.stop()
        elif self.progress_thread is None or not self.progress_thread.is_alive():
            self.start_progress_monitor()
        self.set_resumable_buttons("ready" if self.runner else "idle")

    def initialize_hardware(self):
        if self.runner is not None:
            return

        def work():
            logging.getLogger().setLevel(logging.DEBUG if self.button["Debug"].isChecked() else logging.INFO)
            runner = ResumableExperimentRunner(protocol=self.current_protocol)
            runner.setup_hardware()
            self.runner = runner
            services = ", ".join(runner.services)
            return f"Hardware {services} initialized. Ready to run an experiment"

        self.run_background("Initializing hardware...", work)

    def shutdown_hardware(self):
        if self.runner is None:
            return

        def work():
            self.runner.close()
            self.runner = None
            self.run_active = False
            if self.progress_stop_event is not None:
                self.progress_stop_event.set()
            return "Hardware shut down."

        self.run_background("Shutting down hardware...", work)

    def start(self, preview: bool = False):
        if self.runner is None:
            QMessageBox.warning(self, "Hardware not initialized", "Initialize hardware first.")
            return
        playlist = self.selected_playlist()
        if playlist is None:
            QMessageBox.warning(self, "Missing playlist", "Select a playlist first.")
            return

        def work():
            logging.getLogger().setLevel(logging.DEBUG if self.button["Debug"].isChecked() else logging.INFO)
            if self.progress_stop_event is not None:
                self.progress_stop_event.set()
            if self.progress_thread is not None and self.progress_thread.is_alive():
                self.progress_thread.join(timeout=0.2)
            self.runner.stop_run()
            self.progress_stop_event = threading.Event()
            self.runner.prepare_playlist_run(playlist, preview=preview)
            self.runner.start()
            self.run_active = True
            return "Camera preview running." if preview else "Experiment running."

        self.run_background("Starting experiment...", work)

    def request_stop(self):
        if self.runner is None:
            return

        def work():
            if self.progress_stop_event is not None:
                self.progress_stop_event.set()
            self.runner.stop_run()
            self.run_active = False
            return "Experiment stopped."

        self.run_background("Stopping experiment...", work)

    def camera_preview(self):
        self.start(preview=True)

    def start_progress_monitor(self):
        if self.runner is None or self.progress_stop_event is None:
            return

        def monitor():
            try:
                self.runner.monitor_progress(
                    show_progress=self.button["Progress"].isChecked(),
                    stop_event=self.progress_stop_event,
                )
            finally:
                if self.run_active and self.progress_stop_event is not None and not self.progress_stop_event.is_set():
                    self.runner.stop_run()
                    self.run_active = False
                    self.signals.finished.emit("Experiment finished.")

        self.progress_thread = threading.Thread(target=monitor, daemon=True)
        self.progress_thread.start()

    def set_resumable_buttons(self, state):
        busy = state == "busy"
        ready = self.runner is not None
        running = ready and self.run_active
        self.button["Refresh lists"].setEnabled(not busy and not ready)
        self.button["Initialize hardware"].setEnabled(not busy and not ready)
        self.button["Shutdown hardware"].setEnabled(not busy and ready)
        self.button["Start"].setEnabled(not busy and ready)
        self.button["Stop"].setEnabled(not busy and running)
        self.button["Camera_preview"].setEnabled(not busy and ready)
        self.button["Debug"].setEnabled(not busy)
        self.button["Progress"].setEnabled(not busy)
        self.button["Exit"].setEnabled(not busy)
        self.protocols_view.setEnabled(not busy and not ready)
        self.protocol_view.setEnabled(not busy and not ready)
        self.playlists_view.setEnabled(not busy)
        self.playlist_view.setEnabled(not busy)

    def closeEvent(self, event):
        if self.progress_stop_event is not None:
            self.progress_stop_event.set()
        if self.runner is not None:
            self.runner.close()
            self.runner = None
        self.run_active = False
        event.accept()


def main(protocol_folder: Optional[str] = None, playlist_folder: Optional[str] = None):
    app = QApplication(sys.argv)
    icon = _system_icon(app)
    app.setWindowIcon(icon)

    window = MainWindow(protocol_folder, playlist_folder)
    window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec_())
