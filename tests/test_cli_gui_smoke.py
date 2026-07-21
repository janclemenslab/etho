import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _free_tcp_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run(command, *, env, cwd, timeout=30):
    return subprocess.run(
        command,
        check=True,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _wait_for_nonempty_file(path: Path, *, timeout=5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return True
        time.sleep(0.1)
    return path.is_file() and path.stat().st_size > 0


def test_installed_cli_init_and_run_modified_video_protocol(tmp_path):
    repo_root = _repo_root()
    install_dir = tmp_path / "install"
    home = tmp_path / "home"
    patch_dir = tmp_path / "patch"
    patch_dir.mkdir()

    uv = shutil.which("uv")
    if uv is not None:
        install_command = [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--target",
            str(install_dir),
            "--no-deps",
            str(repo_root),
        ]
    else:
        install_command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(install_dir),
            "--no-deps",
            str(repo_root),
        ]

    _run(install_command, env=os.environ.copy(), cwd=repo_root, timeout=120)

    etho = install_dir / ("Scripts" if os.name == "nt" else "bin") / ("etho.exe" if os.name == "nt" else "etho")
    assert etho.exists()

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PYTHONPATH": str(install_dir),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )

    _run([str(etho), "init"], env=env, cwd=tmp_path)

    config_file = home / "ethoconfig" / "ethoconfig.yml"
    protocol_file = home / "ethoconfig" / "protocols" / "dummy_1min.yml"
    playlist_file = home / "ethoconfig" / "playlists" / "0_silence.txt"
    assert config_file.is_file()
    assert protocol_file.is_file()
    assert playlist_file.is_file()

    protocol = yaml.safe_load(protocol_file.read_text(encoding="utf-8"))
    protocol["maxduration"] = 0.5
    protocol["GCM"].update(
        {
            "frame_rate": 10,
            "frame_width": 64,
            "frame_height": 48,
            "callbacks": {"save_avi": None},
            "port": _free_tcp_port(),
        }
    )
    video_protocol_file = protocol_file.with_name("dummy_video_smoke.yml")
    video_protocol_file.write_text(yaml.safe_dump(protocol), encoding="utf-8")

    # Keep the installed CLI/GCM smoke deterministic in a headless subprocess:
    # the protocol still requests AVI output, but the writer runs inline instead
    # of through the production callback's separate process.
    (patch_dir / "sitecustomize.py").write_text(
        textwrap.dedent(
            """
            from pathlib import Path

            import cv2

            from etho.services.callbacks import callbacks


            class InlineAviWriter:
                def __init__(self, *, file_name, frame_rate, frame_width, frame_height, **kwargs):
                    self.path = Path(file_name + ".avi")
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    size = (int(frame_height), int(frame_width))
                    self.writer = cv2.VideoWriter(
                        str(self.path),
                        cv2.VideoWriter_fourcc(*"x264"),
                        frame_rate,
                        size,
                        True,
                    )
                    if not self.writer.isOpened():
                        raise RuntimeError("Could not open an AVI writer for smoke test.")

                @classmethod
                def make_concurrent(cls, *, task_kwargs, comms="queue"):
                    return cls(**task_kwargs)

                def start(self):
                    pass

                def send(self, data):
                    image = data[0] if isinstance(data, tuple) else data
                    self.writer.write(image)

                def finish(self):
                    pass

                def close(self):
                    self.writer.release()


            callbacks["save_avi"] = InlineAviWriter
            """
        ),
        encoding="utf-8",
    )

    run_env = env.copy()
    run_env["PYTHONPATH"] = os.pathsep.join([str(patch_dir), str(install_dir)])

    save_prefix = "cli_smoke"
    _run(
        [
            str(etho),
            "run",
            str(video_protocol_file),
            str(playlist_file),
            "--save-prefix",
            save_prefix,
            "--no-show-progress",
        ],
        env=run_env,
        cwd=tmp_path,
        timeout=60,
    )

    run_dir = home / "data" / save_prefix
    log_file = run_dir / f"{save_prefix}_gcm.log"
    video_file = run_dir / f"{save_prefix}.avi"
    assert run_dir.is_dir()
    assert log_file.is_file()
    assert video_file.is_file()
    assert _wait_for_nonempty_file(video_file, timeout=15)
    assert "disp" not in protocol["GCM"]["callbacks"]


def test_gui_starts_with_initialized_default_files(tmp_path):
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "PYTHONPATH": str(_repo_root() / "src"),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )
    code = """
    from etho import cli
    cli.init()

    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication
    from etho.app import MainWindow

    app = QApplication([])
    window = MainWindow()
    window.show()
    QTimer.singleShot(50, app.quit)
    app.exec()
    assert window.windowTitle() == "etho control"
    assert window.playlists_view.model().rowCount() >= 1
    assert window.protocols_view.model().rowCount() >= 1
    window.close()
    """
    _run([sys.executable, "-c", textwrap.dedent(code)], env=env, cwd=_repo_root())
