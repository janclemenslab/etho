import sys
import yaml
import rich
import pandas as pd
from pathlib import Path
from typing import Union, Optional
import os
import logging
import time
import psutil, signal

from qtpy import QtWidgets, QtCore
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
)
from qtpy.QtCore import QAbstractTableModel, Qt

from pyqtgraph.parametertree import Parameter, ParameterTree

from ..utils.sound import parse_table
from ..call import client
from ..utils.config import readconfig


logger = logging.getLogger(__name__)


class PandasModel(QAbstractTableModel):
    def __init__(self, data, editable: bool = True):
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
    def __init__(self, model, child=None):
        QTableView.__init__(self)
        self._child = child

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

        # print(self.selected_string)
        import os
        os.system(f'code {self.folder}/{self.selected_string}')
        # os.system('dir')

# format to parametertree
def from_yaml(d):
    pt = []
    for k, v in d.items():
        pt.append({"name": k, "type": "group", "children": []})

        for key, val in v.items():
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

            else:
                item["type"] = type(val).__name__
                item["value"] = val
            pt[-1]["children"].append(item)
    p = Parameter.create(name="params", type="group", children=pt)
    return p


def to_yaml(p):
    rich.print(p.saveState())


def load(filename: str):
    with open(filename, "r") as f:
        d = yaml.load(f, Loader=yaml.Loader)
    return d


def save(d, filename: str):
    pass


def kill_child_processes():
    try:
        parent = psutil.Process()
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for p in children:
        os.kill(p.pid, signal.SIGKILL)


class RunDialog(QDialog):
    def __init__(self, kwargs):
        super().__init__()

        self.setWindowTitle("HELLO!")

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.message = QLabel("Something happened, is that OK?")
        self.layout.addWidget(self.message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        # hide this in a class or function
        # self.p = Process(target=client.client, kwargs=kwargs)  # use process and
        # self.p.start()  # start execution
        # self.p.join()  # join blocks the GUI while the process is running

        self.client = client.client(**kwargs)
        self.services = next(self.client)


    def reject(self):
        logging.info('Cancelling jobs:')
        for service_name, service in self.services.items():
            try:
                logging.info(f'   {service_name}')
                service.finish()
            except:
                logging.warning(f'     Failed.')
        logging.info('   Killing all child processes')
        kill_child_processes()
        logging.info('Done')

        super().reject()

    # @classmethod
    # def do_run(self, method, args=[], kwargs=[], message="Busy doing stuff."):
    #     # self.message.setText(message)
    #     # wx.Yield()  # yield to allow wx to display the dialog
    #     from multiprocessing import Process
    #     # self.Destroy()  # properly destroy the dialog




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
            protocol_folder = config['HEAD']['protocolfolder']
        self.protocol_folder = Path(protocol_folder)

        if not self.protocol_folder.exists():
            raise FileExistsError(f"{self.protocol_folder} does not exist!")

        logging.info(f'Loading protocols from {self.protocol_folder}.')

        if playlist_folder is None:
            config = readconfig()
            playlist_folder = config['HEAD']['playlistfolder']
        self.playlist_folder = Path(playlist_folder)


        if not self.playlist_folder.exists():
            raise FileExistsError(f"{self.playlist_folder} does not exist!")

        logging.info(f'Loading playlists from {self.playlist_folder}.')

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
        self.button["Testimage"] = QCheckBox("Show test image")

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
            raise FileNotFoundError(f'No files found in {self.playlist_folder}.')

        df_playlists = pd.DataFrame({"playlist": sorted([Path(plf).name for plf in playlist_files])})
        playlist_file = Path(playlist_files[0]).name
        playlist_from_filename = lambda filename: parse_table((self.playlist_folder / filename).as_posix())
        playlist_model = PandasModel(playlist_from_filename(playlist_file))
        playlist_model.data_from_filename = playlist_from_filename
        playlist_view = TableView(playlist_model)
        playlist_view.setAlternatingRowColors(True)

        # List of playlist files
        playlists_model = PandasModel(df_playlists, editable=False)
        playlists_view = TableView(playlists_model, playlist_model)
        playlists_view.setAlternatingRowColors(True)
        playlists_view.folder = self.playlist_folder

        # Protocols
        protocol_files = sorted(self.protocol_folder.glob("*.yml"))
        if len(protocol_files) == 0:
            raise FileNotFoundError(f'No files found in {self.protocol_folder}.')

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
        protocols_view = TableView(protocols_model, protocol_view)
        protocols_view.setAlternatingRowColors(True)
        protocols_view.folder = self.protocol_folder

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

        kwargs = {
            "playlistfile": (self.playlist_folder / self.playlists_view.selected_string).as_posix(),
            "protocolfile": (self.protocol_folder / self.protocols_view.selected_string).as_posix(),
            "debug": self.button["Debug"].isChecked(),
            "show_progress": self.button["Progress"].isChecked(),
            "show_test_image": self.button["Testimage"].isChecked(),
            "host": "localhost",
            "save_prefix": None,
            "preview": preview,
            "gui": True,
        }

        rich.print("Starting experiment with these args:")
        rich.print(kwargs)
        # breakpoint()
        # cclient = client.client(**kwargs)
        # services = next(cclient)

        # dlg = RunDialog(kwargs)
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
