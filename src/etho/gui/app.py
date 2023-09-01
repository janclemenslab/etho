import sys
import yaml
import rich
import pandas as pd
from pathlib import Path
from typing import Union, Optional
import os

import qtpy.QtWidgets as QtWidgets
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
)
from qtpy.QtCore import QAbstractTableModel, Qt

from pyqtgraph.parametertree import Parameter, ParameterTree

from ..utils.sound import parse_table
from ..call import client
from ..utils.config import readconfig


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

        header = self.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        self.data = None
        self.selected_string = None

    def update_child(self, selected, deselected):
        if self._child is not None:
            selected_row = selected.indexes()[0].row()
            self.selected_string = str(self.model()._data.iloc[selected_row, 0])
            self.data = self._child.data_from_filename(self.selected_string)
            self._child.replaceData(self.data)


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

        if playlist_folder is None:
            config = readconfig()
            playlist_folder = config['HEAD']['playlistfolder']
        self.playlist_folder = Path(playlist_folder)

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
        self.button["Testimage"] = QCheckBox("Show test image")

        [buttons.addWidget(b) for b in self.button.values()]

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
        playlist_files = sorted(self.playlist_folder.glob("*"))
        df_playlists = pd.DataFrame({"playlist": sorted([Path(plf).name for plf in playlist_files])})
        # Content of selected playlist
        playlist_file = Path(playlist_files[0]).name
        playlist_from_filename = lambda filename: parse_table((self.playlist_folder / filename).as_posix())
        playlist_model = PandasModel(playlist_from_filename(playlist_file))
        playlist_model.data_from_filename = playlist_from_filename
        playlist_view = TableView(playlist_model)
        # List of playlist files
        playlists_model = PandasModel(df_playlists, editable=False)
        playlists_view = TableView(playlists_model, playlist_model)

        # Protocols
        protocol_files = sorted(self.protocol_folder.glob("*"))
        df_protocols = pd.DataFrame({"protocol": sorted([Path(plf).name for plf in protocol_files])})
        # Content of selected protocol file
        protocol_file = Path(protocol_files[1]).name
        protocol_from_filename = lambda filename: from_yaml(load(self.protocol_folder / filename))
        protocol_model = protocol_from_filename(protocol_file)

        protocol_view = ParameterTree()
        protocol_view.setParameters(protocol_model, showTop=False)
        protocol_view.replaceData = protocol_view.setParameters
        protocol_view.data_from_filename = protocol_from_filename

        # List of protocol files
        protocols_model = PandasModel(df_protocols, editable=False)
        protocols_view = TableView(protocols_model, protocol_view)

        if init:
            self.playlist_view = playlist_view
            self.playlists_view = playlists_view
            self.protocol_view = protocol_view
            self.protocols_view = protocols_view
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
        }

        rich.print("Starting experiment with these args:")
        rich.print(kwargs)

        client.client(**kwargs)

    def camera_preview(self):
        self.start(preview=True)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    m = MainWindow()
    m.show()

    sys.exit(app.exec_())
