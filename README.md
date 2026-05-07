# `etho`: A Python framework for coordinating stimuli, data acquisition, and hardware control in neuroscience experiments

[![Test](https://github.com/janclemenslab/etho/actions/workflows/python-package.yml/badge.svg)](https://github.com/janclemenslab/etho/actions/workflows/python-package.yml)
[![Documentation](https://img.shields.io/badge/docs-online-blue)](https://janclemenslab.org/etho)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`etho` is an open-source Python framework for running behavioral neuroscience experiments that require coordinated stimulus presentation, hardware control, data acquisition, and experiment logging.

It was developed for experiments on acoustic communication and social behavior, where multiple hardware devices must operate together with reproducible timing. `etho` coordinates cameras, National Instruments DAQ hardware, acoustic and optogenetic stimulation, environmental sensors, and external imaging systems through a modular service-based architecture.

The software is designed to make experiments reproducible, configurable, and maintainable by separating:
- experiment logic (`protocol.yaml`)
- stimulus definitions (`playlist.txt`)
- hardware calibration
- acquisition callbacks
- service-level logs

from the underlying device code.

---

## Features

- Modular service-based architecture
- Coordinated control of heterogeneous hardware
- Human-readable YAML experiment protocols
- Playlist-based stimulus specification
- Acoustic and optogenetic stimulus generation
- National Instruments DAQ integration
- Multiple camera backends
- Trigger synchronization with external systems (e.g. ScanImage)
- Per-service experiment logging
- HDF5 / Zarr / video data export
- Command-line and GUI interfaces
- Calibration workflows for speakers and LEDs
- Callback system for online display and data processing

---

## Typical use cases

`etho` is intended for experiments requiring synchronized:
- stimulus playback
- analog/digital acquisition
- video recording
- optogenetic stimulation
- trigger generation
- environmental monitoring

Typical applications include:
- acoustic communication experiments
- behavioral neuroscience
- sensory stimulation
- closed-loop experiments
- imaging synchronization
- multimodal behavioral assays

Although originally developed for *Drosophila* experiments, the framework is not species-specific.

---

## Software architecture

The experiment workflow in `etho` is organized around protocols, playlists, services, callbacks, data outputs, and logs.

![etho architecture](docs/figures/etho_software_flow.svg)

1. The user selects an experiment protocol and stimulus playlist.
2. The experiment controller initializes the requested hardware services.
3. Services coordinate acquisition and stimulation during the experiment.
4. Callbacks save and visualize acquired data.
5. Each service writes detailed logs for debugging and provenance tracking.
6. Data, configuration, and logs together form a reproducible experiment record.

---

## Installation

See the full installation guide:

https://janclemenslab.org/etho/install.html

Typical installation:

```bash
conda create -n etho -y python=3.13 uv pip
uv venv etho
source etho/bin/activate
uv pip install etho-python
```

Some hardware backends require additional vendor SDKs and drivers.

---

## Quick start

### Launch GUI

```bash
etho gui
```

### Run an experiment

```bash
etho run protocol.yaml
```

### Example protocol structure

```yaml
maxduration: 600

DAQ:
  samplingrate: 10000
  device: Dev1

CAMERAS:
  frame_rate: 100
```

---

## Documentation

Full documentation is available at:

https://janclemenslab.org/etho

Documentation includes:
- installation
- hardware configuration
- protocol format
- playlists
- calibration
- callbacks
- logging
- API documentation

---

## Development status

`etho` has been under active development since 2018 and is used in ongoing behavioral neuroscience experiments in the Clemens laboratory.

The repository contains:
- automated tests
- continuous integration
- documentation
- example protocols
- public issue tracking

Contributions and bug reports are welcome.

---

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md).

If you encounter problems or would like to request features, please open an issue:
https://github.com/janclemenslab/etho/issues

---

## Citation

If you use `etho` in research, please cite:

```bibtex
TODO
```

A JOSS paper describing the software is currently in preparation.

---

## License

MIT License.
