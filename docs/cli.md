# Command-Line Interface

The installed console command is `etho`. The public interface exposes four
subcommands. Examples on this page assume a Windows rig and PowerShell.

```text
usage: etho [-h] {version,init,run,gui} ...

positional arguments:
  {version,init,run,gui}
    version             Displays system, version, and hardware info.
    init                Initializes config files and folders.
    run                 Starts an experiment from the CLI.
    gui                 Opens the graphical user interface.

options:
  -h, --help            show this help message and exit
```

## Initialize Configuration

```text
usage: etho init [-h]

Initializes config files and folders.

options:
  -h, --help  show this help message and exit
```

Run this once per user account:

```powershell
etho init
```

It creates `%USERPROFILE%\ethoconfig\ethoconfig.yml`, protocol and playlist
folders, a stimulus folder, and example files for a dummy-camera run.

## Start the GUI

```text
usage: etho gui [-h] [protocol_folder] [playlist_folder]

Opens the graphical user interface.

positional arguments:
  protocol_folder  Folder with protocol files.
                   Defaults to value ['HEAD']['protocolfolder'] from %USERPROFILE%\ethoconfig\ethoconfig.yml.
  playlist_folder  Folder with playlist files.
                   Defaults to value ['HEAD']['playlistfolder'] from %USERPROFILE%\ethoconfig\ethoconfig.yml.

options:
  -h, --help       show this help message and exit
```

Typical usage:

```powershell
etho gui
etho gui "$HOME\ethoconfig\protocols" "$HOME\ethoconfig\playlists"
```

## Run an Experiment

```text
usage: etho run [-h] [--save-prefix SAVE_PREFIX]
                [--show-progress | --no-show-progress]
                [-d | --debug | --no-debug] [-p | --preview | --no-preview]
                protocolfile [playlistfile]

Starts an experiment from the CLI.

positional arguments:
  protocolfile
  playlistfile

options:
  -h, --help            show this help message and exit
  --save-prefix SAVE_PREFIX
  --show-progress, --no-show-progress
  -d, --debug, --no-debug
  -p, --preview, --no-preview
```

Run a camera-only protocol:

```powershell
etho run "$HOME\ethoconfig\protocols\dummy_1min.yml" --save-prefix test_camera
```

Run a protocol that includes a DAQ service and therefore needs a playlist:

```powershell
etho run "$HOME\ethoconfig\protocols\my_protocol.yml" "$HOME\ethoconfig\playlists\my_playlist.txt" --save-prefix session_001
```

Use `--preview` for camera alignment. Preview mode disables saving and logging
for the camera run and replaces configured camera callbacks with a display
callback.

## Display System Support

```text
usage: etho version [-h] [-d | --debug | --no-debug]

Displays system, version, and hardware info.

options:
  -h, --help            show this help message and exit
  -d, --debug, --no-debug
                        Display exception info for failed imports. Defaults to False.
```

Run:

```powershell
etho version
etho version --debug
```

Use the debug form when a rig dependency is expected to be available but appears
as missing.
