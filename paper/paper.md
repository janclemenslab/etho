---
title: '`etho`: A Python framework for coordinating stimuli, data acquisition, and hardware control in neuroscience experiments'
tags:
  - Python
  - neuroscience
  - behavior
  - audio
  - ScanImage
  - optogenetics
  - calcium imaging
  - camera
authors:
  - name: Jan Clemens
    orcid: 0000-0003-4200-8097
    affiliation: 1
affiliations:
 - name: Carl von Ossietzky University, Oldenburg, Germany
   index: 1
   ror: 033n9gh91
date: 10 May 2026
bibliography: bib.bib

---


# Summary

`Etho` is an open-source Python package for running behavioral and neuroscience experiments that require coordinated stimulus presentation, hardware control, and data acquisition. It was developed for experiments combining stimulus playback, analog and digital input/output, video acquisition, optogenetic stimulation, environmental monitoring, and external imaging systems. The package is user-friendly and does not require programming skills for configuration or operation. It provides text-based configuration through both a command-line interface and a graphical user interface for running experiments.

The central use case for `etho` is a laboratory experiment in which multiple devices must operate together with reproducible timing. For example, an experiment can present calibrated acoustic and optogenetic stimuli through National Instruments data-acquisition hardware, record multichannel microphone and trigger signals, acquire synchronized camera frames, and send control pulses to external systems such as ScanImage [@Pologruto_2003_scanimage]. After the experiment, the timing relationships between stimuli, recordings, and control signals remain available for downstream annotation and analysis. Experimental logic is specified in human-readable YAML protocol files and tabular stimulus playlists, separating scientific design from low-level device code and making experiments easier to inspect, modify, archive, and reproduce.


# Statement of need

Behavioral neuroscience experiments are inherently multimodal. Experiments often combine controlled sensory stimulation, high-speed video, electrophysiology, optical imaging, optogenetics, and environmental monitoring. Commercial acquisition software and vendor-specific device tools can control individual hardware components, but are often poorly suited for experiments that require flexible coordination across heterogeneous systems.

Labs therefore often resort to custom scripts to integrate heterogeneous hardware environments. While such scripts can be flexible, they are often difficult to reuse across rigs, users, and projects, especially when experiments involve multiple asynchronous data streams and require precise logging of stimuli, timing, and metadata. These challenges are particularly acute in academic environments, where personnel turnover every 2–5 years can make long-term maintenance and reproducibility difficult. In addition, custom scripts often store metadata in idiosyncratic formats, limiting interoperability and complicating data reuse. Flexible, reproducible, and user-friendly experiment control software is therefore needed.

`etho`addresses this gap by providing a configurable Python framework for multi-device behavioral experiments. It is designed for laboratories that run repeated experimental protocols across one or more rigs and require the flexibility of a programmable system without embedding all experimental logic directly in scripts. In contrast to vendor-specific solutions, the system is hardware-agnostic and extensible, allowing it to adapt as new hardware devices and experimental paradigms are introduced.

In `etho`, protocols define hardware configurations and acquisition settings, while stimulus playlists specify trial structure and stimulus parameters. This separation supports systematic experimental variation while keeping hardware settings, calibration information, and acquired data tightly linked and reproducibly associated with each experiment.


# State of the field

Several open-source systems address parts of the experimental control problem, but they differ substantially in scope and design goals. Bonsai provides a powerful visual programming environment for asynchronous acquisition, online processing, and closed-loop control of data streams [@Lopes_2015_bonsai]. However, its workflow-centric design can make large experimental protocols difficult to standardize, version, and reuse across users and rigs, particularly when experiments require structured management of hardware configurations, stimulus playlists, and metadata. pyControl focuses on specifying behavioral tasks as microcontroller-based state machines together with tools for managing parallel setups [@Akam_2022_opensource], but is optimized for discrete trial logic rather than coordinated acquisition across heterogeneous devices such as cameras, audio interfaces, environmental sensors, and external imaging systems. Autopilot emphasizes distributed behavioral experiments using networked Raspberry Pis [@Saunders_2019_autopilot], but is less suited for experiments requiring high-bandwidth synchronized acquisition or integration with specialized laboratory hardware. Bpod provides temporally precise control for trial-based rodent experiments through microcontroller-driven state machines [@Solari_2018_open], but does not aim to provide a general framework for multimodal acquisition and hardware orchestration. PsychoPy is widely used for visual and auditory stimulus presentation in psychophysics and human behavioral experiments [@Peirce_2019_psychopy2], but focuses primarily on stimulus delivery rather than coordinated control of diverse experimental hardware and multimodal data streams.

`Etho`complements these tools by focusing on reproducible coordination of heterogeneous laboratory hardware within a pragmatic Python framework. Rather than replacing existing acquisition or stimulus-generation software, it provides an architectural layer that organizes experiments around structured protocol, playlist, calibration, and log files. This design enables experiments to combine stimulus generation, analog and digital acquisition, camera recording, environmental monitoring, and external triggers while retaining direct Python-level control and support for lab-specific hardware extensions. Existing tools can therefore be integrated into `etho`workflows when appropriate, for example by using PsychoPy for calibrated visual stimulus generation. The primary contribution of `etho`is thus not a new standalone device-control system, but a flexible framework for coordinating multimodal experiments in a reproducible and extensible manner.


# Software design

`etho` is organized modularly around __services__, __protocols__, __playlists__, and __callbacks__ (\autoref{fig:flow}).
Services define hardware interfaces. An experiment is defined by a protocol and a playlist. Protocols list and parameterize services and callbacks for processing and saving acquired data. Playlists specify trial structure and stimuli.

__Services__ encapsulate hardware-specific functionality. Current service classes include support for multiple camera backends, National Instruments data-acquisition boards, sound playback, optogenetic LED control, environmental monitoring, DLP-projector stimulation, and remote control of ScanImage calcium imaging rigs.

![__`etho` software structure and data flow:__ Command-line and graphical user interfaces allow users to select configuration files and run experiments. Protocol and playlist configuration files define and parameterize hardware and stimuli for each experiment. Hardware services control and log connected devices, while callbacks display and save data streams generated during experiments. Together, configuration files, logs, and acquired data form a standardized experimental record that can be further processed and analyzed.\label{fig:flow}](fig_flow.pdf)

__Protocols__ are YAML files that define the structure of an experiment. A protocol specifies the experiment duration, active services, service-specific configurations, and callbacks. For example, a protocol can configure a camera service with frame rate, region of interest, exposure, and video-saving callbacks, while also configuring a data-acquisition service with sampling rate, analog input channels, analog and digital output channels, and callbacks for Zarr [@Miles_2020_zarrdevelopers] data storage. Because protocols are plain text, they can be version controlled and stored alongside data and analysis code.

This modular service-plus-protocol structure makes `etho` easily extensible: New hardware can be added as new Python classes implementing the service interface and registering a new service. The new service can then be added to a protocol and used in an experiment.

__Playlists__ are tabular files that define trial sequences. They can reference fixed, external waveform files or simple runtime-generated stimuli, such as sinusoids, optogenetic LED pulse trains, hardware clock signals, and hardware trigger pulses. Playlists support multichannel stimulation with per-channel parameters. Speaker and LED calibration files convert requested stimulus intensities into device-specific output amplitudes, helping preserve quantitative stimulus control across rigs.

__Callbacks__ process data produced by services and are specified in the protocols. Camera services can display frames, save video, and save timestamps; data-acquisition services can save analog data or plot traces. The callbacks also define standardized formats for data and metadata, facilitating long-term data reuse.

In addition, `etho` writes separate logs for each service, recording service-specific events, parameters, warnings, and errors during an experiment. These logs provide an audit trail for diagnosing hardware or timing problems and help connect acquired data to the processes that produced them. The callback and logging mechanisms separate data acquisition, online monitoring, and experiment provenance from low-level hardware control code.

Services and callbacks run in independent processes, thus making use of modern multi-core hardware. This concurrency is what makes `etho` fast, enabling precise synchronized stimulus presentation and real-time, high-speed video compression using GPUs.

The modular service-process architecture makes the system reusable across rigs and labs and maintainable in the long term. Explicit protocol and playlist files and standardized data formats encourage reproducibility, traceability, and reuse of experiments.


# Research impact

`Etho` is currently used in the Roemschied, Deutsch, and Clemens laboratories to run behavioral and neuroscience experiments on acoustic communication, sensory and motor processing, and social behavior [@Vijendravarma_2022_drosophila; @Steinfath_2025_neural; @Palacios_2025_drosophila; @RavindranNair_2026_sexspecific]. Its documentation includes installation instructions, protocol and playlist formats, GUI and command-line usage, and API references, making the software accessible and broadly usable.

The value of `etho`lies in making complex experiments easier to run, maintain, and reproduce. By organizing experimental configuration, acquired data, calibration information, and log files into structured, versionable formats within a reusable Python package, `etho`reduces dependence on one-off scripts and ad-hoc hardware integration. This organization enforces best practices, improves reproducibility, facilitates reuse across rigs and users, and supports more transparent reporting of experimental methods and acquisition parameters.


# AI usage disclosure

During the preparation of this work, the author used ChatGPT to assist with language and phrasing throughout the manuscript. ChatGPT and codex were also used for drafting the documentation and for refactoring code. After using these services, the author reviewed and edited the content as needed and takes full responsibility for the content of the publication and the software.


# Acknowledgements

We thank past and current members of the Roemschied, Deutsch, and Clemens labs for testing `etho` on experimental rigs and reporting bugs. Development of `etho` was funded via an Emmy Noether Grant (Project number 329518246) and an ERC Starting Grant (Grant agreement No. 851210) to JC.


# References
