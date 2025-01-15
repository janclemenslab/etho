import sys
import yaml
import rich
import pandas as pd
from pathlib import Path
from typing import Union, Optional
import os
import logging
import time
import psutil
import threading
import queue

from qtpy import QtWidgets
from qtpy.QtWidgets import (
    QApplication,
    QTableView,
    QGridLayout,
    QWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QCheckBox,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QSplitter,
    QProgressBar,
)

from qtpy.QtCore import QAbstractTableModel, Qt

from pyqtgraph.parametertree import Parameter, ParameterTree

from .utils.sound import parse_table
from . import client
from .utils.config import readconfig


logger = logging.getLogger(__name__)


class PandasModel(QAbstractTableModel):
    def __init__(self, data, editable: bool = False):
        QAbstractTableModel.__init__(self)
        self._data = data
        self._editable = editable

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                value = self._data.iloc[index.row(), index.column()]
                return str(value)

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            self._data.iloc[index.row(), index.column()] = value
            return True

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._data.columns[col]
        return None

    def flags(self, index):
        if self._editable:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def replaceData(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()


class TableView(QTableView):
    def __init__(self, model, child=None, folder=None):
        QTableView.__init__(self)
        self._child = child
        self._folder = folder

        self.setModel(model)
        self.selectionModel().selectionChanged.connect(self.update_child)
        self.doubleClicked.connect(self.edit_file)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.resizeRowsToContents()
        self.data = None
        self.selected_string = None

    def update_child(self, selected, deselected):
        if self._child is not None:
            selected_row = selected.indexes()[0].row()
            self.selected_string = str(self.model()._data.iloc[selected_row, 0])
            self.data = self._child.data_from_filename(self.selected_string)
            self._child.replaceData(self.data)

    def edit_file(self):
        if self._folder is not None:
            print(f"code {self.folder}/{self.selected_string}")
            os.system(f"code {self.folder}/{self.selected_string}")


# format to parametertree
def from_yaml(d, readonly=True):
    pt = []
    for key, val in d.items():
        item = {"name": key}
        if isinstance(val, list):
            item["type"] = "group"
            item["original_type"] = list
            item["children"] = [{"name": str(it), "type": "bool", "value": True} for it in val]
        if isinstance(val, dict):
            # for callbacks, value is a dict - add key val of that as list
            item["type"] = "group"
            item["original_type"] = dict
            item["children"] = []
            for val_key, val_val in val.items():
                child_item = {
                    "name": str(val_key),
                    "type": "str",
                    "value": str(val_val),
                }
                item["children"].append(child_item)
        elif val is None:  # Fall back for None values
            item["type"] = "str"
            item["value"] = str(val)
        else:
            item["type"] = type(val).__name__
            item["value"] = val
        pt.append(item)
    p = Parameter.create(name="Protocol parameters", type="group", children=pt)
    if readonly:
        children_read_only(p.children())
    return p


def children_read_only(children):
    for child in children:
        if child.children():
            children_read_only(child.children())
        else:
            child.setReadonly()


def to_yaml(p):
    # TODO: unwrap this recursively into a hierarcchy of dictionaries
    rich.print(p.saveState()["children"])


def load(filename: str):
    with open(filename, "r") as f:
        d = yaml.load(f, Loader=yaml.SafeLoader)
    return d


def save(d, filename: str):
    pass


def kill_child_processes():
    try:
        parent = psutil.Process()
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for child in children:
        child.terminate()  # friendly termination
    _, still_alive = psutil.wait_procs(children, timeout=3)
    for child in still_alive:
        child.kill()  # unfriendly termination
        # os.kill(child.pid, signal.SIGKILL)


class RunDialog(QDialog):
    def __init__(self, stop_event, done_event, queue_total):
        super().__init__()

        self.stop_event = stop_event
        self.done_event = done_event
        self.queue_total = queue_total

        self.setWindowTitle("Progress")

        QBtn = QDialogButtonBox.Cancel

        self.message = QLabel("Running")
        self.message.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.pbar = QProgressBar(self)
        self.pbar.setValue(0)

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.message)
        self.layout.addWidget(self.pbar)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
        self.total = queue_total.get()

        self.monitor_thread = threading.Thread(
            target=monitor,
            args=[self.done_event, self.stop_event, self.accept, self.pbar, self.total],
        )
        self.monitor_thread.start()

    def reject(self):
        self.stop_event.set()
        super().reject()

    def accept(self):
        self.stop_event.set()
        super().accept()


def monitor(event1, event2, callback, progress=None, progress_total=100):
    cnt = 0
    RUN = True
    while RUN:
        if event1.is_set():
            callback()
            RUN = False
        if event2.is_set():
            RUN = False
        cnt += 1
        if progress is not None:
            progress.setValue(int(100 * cnt / progress_total))
        time.sleep(1)


class MainWindow(QMainWindow):
    def __init__(
        self,
        protocol_folder: Optional[Union[str, os.PathLike]] = None,
        playlist_folder: Optional[Union[str, os.PathLike]] = None,
    ):
        super(MainWindow, self).__init__()

        # rich.print(config)
        if protocol_folder is None:
            config = readconfig()
            protocol_folder = config["protocolfolder"]
        self.protocol_folder = Path(protocol_folder)

        if not self.protocol_folder.exists():
            raise FileExistsError(f"{self.protocol_folder} does not exist!")

        logging.info(f"Loading protocols from {self.protocol_folder}.")

        if playlist_folder is None:
            config = readconfig()
            playlist_folder = config["playlistfolder"]
        self.playlist_folder = Path(playlist_folder)

        if not self.playlist_folder.exists():
            raise FileExistsError(f"{self.playlist_folder} does not exist!")

        logging.info(f"Loading playlists from {self.playlist_folder}.")

        self.setWindowTitle("etho control")

        # Buttons
        buttons = QVBoxLayout()
        self.button = {}
        self.button["Refresh lists"] = QPushButton("Refresh lists")
        self.button["Refresh lists"].clicked.connect(self.refresh_lists)
        self.button["Start"] = QPushButton("Start")
        self.button["Start"].clicked.connect(self.start)
        self.button["Camera_preview"] = QPushButton("Camera preview")
        self.button["Camera_preview"].clicked.connect(self.camera_preview)
        self.button["Debug"] = QCheckBox("Debug")
        self.button["Progress"] = QCheckBox("Show Progress")
        self.button["Progress"].setChecked(True)

        [buttons.addWidget(b) for b in self.button.values()]

        self.help = QtWidgets.QLabel(
            "<br>"
            "<br>"
            "<B>Instructions</B><br>"
            "<br>"
            "Single Click on<br>"
            " playlist or protocol.<br>"
            "previews the file.<br>"
            "<br>"
            "Double Click opens<br>"
            "playlist or protocol<br>"
            "in VS code.<br>"
        )
        buttons.addWidget(self.help)

        # Layout
        self.layout = QGridLayout()
        self.layout.addLayout(buttons, 0, 0)
        self.refresh_lists(init=True)

        self.layout.setColumnMinimumWidth(1, 200)
        self.layout.setColumnMinimumWidth(2, 600)
        self.layout.setColumnStretch(2, 1)
        self.layout.setColumnStretch(1, 2)

        widget = QWidget()
        widget.setLayout(self.layout)
        self.setCentralWidget(widget)

    def refresh_lists(self, init: bool = False):
        playlist_files = sorted(self.playlist_folder.glob("*.txt"))
        if len(playlist_files) == 0:
            raise FileNotFoundError(f"No files found in {self.playlist_folder}.")

        df_playlists = pd.DataFrame({"playlist": sorted([Path(plf).name for plf in playlist_files])})
        playlist_file = Path(playlist_files[0]).name
        playlist_from_filename = lambda filename: parse_table((self.playlist_folder / filename).as_posix())
        playlist_model = PandasModel(playlist_from_filename(playlist_file))
        playlist_model.data_from_filename = playlist_from_filename
        playlist_view = TableView(playlist_model)
        playlist_view.setAlternatingRowColors(True)

        # List of playlist files
        playlists_model = PandasModel(df_playlists, editable=False)
        playlists_view = TableView(playlists_model, playlist_model, self.playlist_folder)
        playlists_view.setAlternatingRowColors(True)
        playlists_view.folder = self.playlist_folder
        playlists_view.selectRow(0)

        # Protocols
        protocol_files = sorted(self.protocol_folder.glob("*.yml"))
        if len(protocol_files) == 0:
            raise FileNotFoundError(f"No files found in {self.protocol_folder}.")

        df_protocols = pd.DataFrame({"protocol": sorted([Path(plf).name for plf in protocol_files])})
        # Content of selected protocol file
        protocol_file = Path(protocol_files[0]).name
        protocol_from_filename = lambda filename: from_yaml(load(self.protocol_folder / filename))
        protocol_model = protocol_from_filename(protocol_file)

        protocol_view = ParameterTree()
        protocol_view.setParameters(protocol_model, showTop=False)
        protocol_view.replaceData = protocol_view.setParameters
        protocol_view.data_from_filename = protocol_from_filename

        # List of protocol files
        protocols_model = PandasModel(df_protocols, editable=False)
        protocols_view = TableView(protocols_model, protocol_view, self.protocol_folder)
        protocols_view.setAlternatingRowColors(True)
        protocols_view.folder = self.protocol_folder
        protocols_view.selectRow(0)

        if init:
            self.playlist_view = playlist_view
            self.playlists_view = playlists_view
            self.protocol_view = protocol_view
            self.protocols_view = protocols_view
            # splitter = QSplitter(QtCore.Qt.Vertical)
            # splitter.addWidget(self.playlists_view)
            # splitter.addWidget(self.protocols_view)

            # # self.layout.addWidget(splitter)

            # splitter2 = QSplitter(QtCore.Qt.Vertical)
            # splitter2.addWidget(self.playlist_view)
            # splitter2.addWidget(self.protocol_view)

            # splitterH = QSplitter(QtCore.Qt.Horizontal)
            # splitterH.addWidget(splitter)
            # splitterH.addWidget(splitter2)
            # self.layout.addWidget(splitterH, 0, 1, 1, 1)

            self.layout.addWidget(self.playlists_view, 0, 1, 1, 1)
            self.layout.addWidget(self.playlist_view, 0, 2, 1, 5)
            self.layout.addWidget(self.protocols_view, 1, 1, 1, 1)
            self.layout.addWidget(self.protocol_view, 1, 2, 1, 5)
        else:
            self.layout.replaceWidget(self.playlists_view, playlists_view)
            self.layout.replaceWidget(self.playlist_view, playlist_view)
            self.layout.replaceWidget(self.protocols_view, protocols_view)
            self.layout.replaceWidget(self.protocol_view, protocol_view)
            self.playlist_view = playlist_view
            self.playlists_view = playlists_view
            self.protocol_view = protocol_view
            self.protocols_view = protocols_view

    def start(self, preview: bool = False):
        msg = []
        if self.playlists_view.selected_string is None:
            msg.append("playlist")

        if self.protocols_view.selected_string is None:
            msg.append("protocol")

        if len(msg):
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Error: Could not start the experiment.")
            dlg.setText(f"Please select a {' and a '.join(msg)}.")
            dlg.exec_()
            return

        stop_event = threading.Event()
        done_event = threading.Event()
        queue_total = queue.Queue()

        kwargs = {
            "playlistfile": (self.playlist_folder / self.playlists_view.selected_string).as_posix(),
            "protocolfile": (self.protocol_folder / self.protocols_view.selected_string).as_posix(),
            "debug": self.button["Debug"].isChecked(),
            "show_progress": self.button["Progress"].isChecked(),
            "save_prefix": None,
            "preview": preview,
            "_stop_event": stop_event,
            "_done_event": done_event,
            "_queue": queue_total,
        }

        rich.print("Starting experiment with these args:")
        rich.print(kwargs)

        t = threading.Thread(target=client.client, kwargs=kwargs)
        t.start()

        # dlg = RunDialog(stop_event, done_event, queue_total)
        # dlg.exec_()

    def camera_preview(self):
        self.start(preview=True)


def main(protocol_folder: Optional[str] = None, playlist_folder: Optional[str] = None):
    """Opens the graphical user interface.

    Args:
        protocol_folder (Optional[str]): Folder with protocol files.
                                         Defaults to value ['HEAD']['protocolfolder'] from `~/ethoconfig.yml`.
        playlist_folder (Optional[str]): Folder with playlist files.
                                         Defaults to value ['HEAD']['playlistfolder'] from `~/ethoconfig.yml`.
    """
    app = QApplication(sys.argv)

    m = MainWindow(protocol_folder, playlist_folder)
    m.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
