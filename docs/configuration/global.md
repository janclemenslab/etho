(global-configuration)=
# Global Configuration

The global configuration lives at `~/ethoconfig/ethoconfig.yml`. It is created
by:

```shell
etho init
```

Example:

```yaml
user: ncb
savefolder: /Users/USER/data
python_exe: /Users/USER/miniforge3/envs/etho/bin/python
playlistfolder: /Users/USER/ethoconfig/playlists
protocolfolder: /Users/USER/ethoconfig/protocols
stimfolder: /Users/USER/ethoconfig/stim
ATTENUATION:
  -1: 1
  0: 1
  100: 1
```

Fields:

- `savefolder`: Parent folder for experiment output directories.
- `python_exe`: Python executable used when services are started. This should usually point to the `etho` conda environment.
- `playlistfolder`: Default folder shown by the GUI for playlist files.
- `protocolfolder`: Default folder shown by the GUI for protocol files.
- `stimfolder`: Folder used to resolve stimulus files referenced by playlists.
- `ATTENUATION`: Frequency-keyed attenuation factors used when loading stimuli.
- `user`: Optional user or rig label.

Protocol files can override `python_exe` for a service if a specific service
must run in a different environment. Per-service remote host blocks are no
longer supported.
