# Installation

Etho is a Python package with optional hardware SDK dependencies. Use conda for
the base environment and `uv pip install` for Python packages.

## Recommended Rig Environment

Use this environment for rigs that may need FLIR/Spinnaker support. As of March
2026, the FLIR Python driver is expected to require Python 3.10.

```shell
conda create -n etho -c conda-forge -y \
  python=3.10 "numpy<2" scipy h5py opencv pandas pyzmq gevent future \
  pillow msgpack-python pyyaml ipython uv pip git defopt msgpack-numpy \
  rich psutil pydaqmx pyqtgraph qtpy pyside6-essentials zarr
conda activate etho
uv pip install zerorpc-numpy etho-python --no-deps
```

The `--no-deps` install keeps conda-owned packages in control and only installs
the packages that are not available from the conda command above.

## Lightweight Environment

For a workstation that only needs docs, configuration editing, or the dummy
camera workflow:

```shell
conda create -n etho -c conda-forge -y python=3.13 uv git ffmpeg
conda activate etho
uv pip install etho-python
```

Use the rig environment instead if you need vendor camera SDKs, NI DAQ hardware,
or GUI behavior that has only been validated on Python 3.10.

## Source Checkout

From a local checkout:

```shell
conda activate etho
uv pip install -e ".[dev,doc]"
```

Build the documentation with:

```shell
sphinx-build -b html docs /tmp/etho-docs-html
```

## Optional Hardware Packages

Install only the packages and vendor drivers required by the rig:

- Ximea cameras: install the Ximea driver and Python package from Ximea.
- FLIR/Spinnaker cameras: install the Spinnaker SDK and the matching Python package from FLIR.
- Basler cameras: install Basler pylon and `pypylon`.
- Hamamatsu DCAM cameras: install the DCAM driver and `pylablib`.
- National Instruments DAQ: install NI-DAQmx and ensure `pydaqmx` can import in the `etho` environment.
- LightCrafter/DLP projector rigs: install the projector control software used by the rig and verify whether `pycrafter4500` is required for that setup.
- Video writing through VidGear: install `vidgear[core]` if the protocol uses VidGear callbacks.

After installing optional SDKs, run:

```shell
etho version --debug
```

Missing optional hardware entries are expected on machines that do not operate
that hardware.

## Initialization

Activate the environment and initialize config files and folders:

```shell
conda activate etho
etho init
```

This creates `~/data` for saved runs and `~/ethoconfig` with:

- `ethoconfig.yml` for [global configuration](configuration/global.md)
- `playlists/` for [stimulation playlists](configuration/playlist.md)
- `protocols/` for [experimental protocols](configuration/protocol.md)
- `stim/` for stimulus files such as WAV files

Start the GUI with:

```shell
etho gui
```
