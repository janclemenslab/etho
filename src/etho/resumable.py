import copy
import logging
import time
from pathlib import Path

import numpy as np
import rich
from rich.progress import Progress

from . import config
from .services import service_base_name
from .services.resumable import ResumableDAQ, ResumableGCM
from .utils.tui import rich_information
from .utils.config import defaultify, readconfig
from .utils.sound import build_playlist, load_sounds, parse_table


logger = logging.getLogger(__name__)


def _attenuation_for_host():
    attenuation = config["ATTENUATION"]
    host = config["host"] or "localhost"
    if isinstance(attenuation, dict) and host in attenuation:
        return attenuation[host]
    return attenuation


def _playlist_cache_key(protocol, playlistfile):
    daq_name = next((name for name in protocol["use_services"] if service_base_name(name) == "DAQ"), None)
    if daq_name is None:
        return None
    daq_params = protocol[daq_name]
    attenuation = _attenuation_for_host()
    return (
        daq_name,
        str(Path(playlistfile).resolve()),
        daq_params["samplingrate"],
        str(config["stimfolder"]),
        repr(attenuation),
    )


def playlist_arrays(protocol, playlistfile, cache=None):
    daq_name = next((name for name in protocol["use_services"] if service_base_name(name) == "DAQ"), None)
    if daq_name is None:
        return None, None, protocol["maxduration"]

    daq_params = protocol[daq_name]
    fs = daq_params["samplingrate"]
    cache_key = _playlist_cache_key(protocol, playlistfile)
    if cache is not None and cache_key in cache:
        playlist, sounds = cache[cache_key]
        logger.info(f"Reusing loaded stimuli for {playlistfile}.")
    else:
        playlist = parse_table(playlistfile)
        attenuation = _attenuation_for_host()
        sounds = load_sounds(playlist, fs, attenuation=attenuation, stimfolder=config["stimfolder"])
        sounds = [sound.astype(np.float64) for sound in sounds]
        if cache is not None:
            cache[cache_key] = (playlist, sounds)
    playlist_items, duration = build_playlist(sounds, protocol["maxduration"], fs, shuffle=daq_params["shuffle"])
    data = np.concatenate([sounds[item] for item in playlist_items], axis=0)

    nb_digital = len(daq_params["digital_chans_out"] or [])
    if nb_digital:
        return data[:, :-nb_digital], data[:, -nb_digital:].astype(np.uint8), duration
    return data, None, duration


class ResumableExperimentRunner:
    def __init__(self, protocolfile=None, *, protocol=None, save_prefix_root=None):
        if protocolfile is None and protocol is None:
            raise ValueError("Provide protocolfile or protocol.")
        self.protocolfile = protocolfile
        self.protocol = copy.deepcopy(protocol) if protocol is not None else None
        self.save_prefix_root = save_prefix_root
        self.run_count = 0
        self.services = {}
        self._playlist_cache = {}

    def setup_hardware(self):
        prot = defaultify(copy.deepcopy(self.protocol)) if self.protocol is not None else readconfig(self.protocolfile)
        self.prot = prot
        defaults = config
        if defaults["host"] is None:
            defaults["host"] = "localhost"
        rich.print(defaults)
        logger.info("Setting up resumable hardware.")
        for service_name in prot["use_services"]:
            base = service_base_name(service_name)
            logger.info(f"   {service_name}.")
            if base == "GCM":
                self.services[service_name] = ResumableGCM(prot[service_name]).setup_hardware()
            elif base == "DAQ":
                self.services[service_name] = ResumableDAQ(prot[service_name]).setup_hardware()
            else:
                raise ValueError(f"Resumable runner only supports DAQ and GCM, got {service_name}.")
        services = ", ".join(prot["use_services"])
        logger.info(f"Hardware {services} initialized. Ready to run an experiment")
        self.print_information()
        return self

    def print_information(self):
        for key, service in self.services.items():
            if hasattr(service, "information"):
                rich_information(service.information(), prefix=key)

    def prepare_run(
        self,
        save_prefix=None,
        analog_data_out=None,
        digital_data_out=None,
        duration=None,
        metadata=None,
        preview=False,
    ):
        if not self.services:
            self.setup_hardware()
        self.run_count += 1
        if save_prefix is None:
            if self.save_prefix_root is not None:
                save_prefix = self.save_prefix_root
            else:
                save_prefix = f"{config['host'] or 'localhost'}-{time.strftime('%Y%m%d_%H%M%S')}"

        savefolder = Path(config["savefolder"] or ".")
        if self.save_prefix_root is None:
            while (savefolder / save_prefix).exists():
                time.sleep(1)
                save_prefix = f"{config['host'] or 'localhost'}-{time.strftime('%Y%m%d_%H%M%S')}"
        run_duration = duration
        if run_duration is None and self.prot["maxduration"] > 0:
            run_duration = self.prot["maxduration"]
        if run_duration is None:
            n_samples = 0
            if analog_data_out is not None:
                n_samples = analog_data_out.shape[0]
            if digital_data_out is not None:
                n_samples = max(n_samples, digital_data_out.shape[0])
            for service in self.services.values():
                if isinstance(service, ResumableDAQ) and n_samples:
                    run_duration = n_samples / service.fs
        if run_duration is None:
            raise ValueError("Provide duration or DAQ output arrays so run duration can be inferred.")
        if preview:
            run_duration = 1_000_000

        run_folder = savefolder / save_prefix
        run_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Preparing resumable experiment {save_prefix}.")
        service_counts = {}
        for service_name, service in self.services.items():
            service_type = service_base_name(service_name)
            service_index = service_counts.get(service_type, 0)
            service_counts[service_type] = service_index + 1
            save_suffix = f"_{service_index + 1}" if service_index > 0 else ""
            savefilename = run_folder / f"{save_prefix}{save_suffix}"
            if isinstance(service, ResumableGCM):
                logger.info(f"   preparing {service_name}.")
                service.prepare_run(str(savefilename), run_duration + 10, preview=preview)
            elif isinstance(service, ResumableDAQ):
                if preview:
                    logger.info(f"   skipping {service_name} for preview.")
                    service.stop_run()
                    continue
                logger.info(f"   preparing {service_name}.")
                service.prepare_run(
                    str(savefilename),
                    analog_data_out=analog_data_out,
                    digital_data_out=digital_data_out,
                    duration=run_duration,
                    metadata=metadata,
                )
        self.print_information()
        return self

    def prepare_playlist_run(self, playlistfile, save_prefix=None, metadata=None, preview=False):
        analog_data_out, digital_data_out, duration = playlist_arrays(self.prot, playlistfile, cache=self._playlist_cache)
        return self.prepare_run(
            save_prefix=save_prefix,
            analog_data_out=analog_data_out,
            digital_data_out=digital_data_out,
            duration=duration,
            metadata=metadata,
            preview=preview,
        )

    def start(self):
        logger.info("Starting resumable experiment.")
        for service in self.services.values():
            if isinstance(service, ResumableGCM):
                service.start()
        time.sleep(0.5)
        for service in self.services.values():
            if isinstance(service, ResumableDAQ) and getattr(service, "state", "prepared") == "prepared":
                service.start()
        logger.info("Resumable experiment running.")
        return self

    def stop_run(self):
        logger.info("Stopping resumable experiment.")
        for service in self.services.values():
            if isinstance(service, ResumableDAQ):
                service.stop_run()
        for service in self.services.values():
            if isinstance(service, ResumableGCM):
                service.stop_run()
        logger.info("Resumable experiment stopped.")
        return self

    def close(self):
        logger.info("Shutting down resumable hardware.")
        for service in self.services.values():
            service.close()
        logger.info("Resumable hardware shut down.")
        return self

    def progress(self):
        progress = {}
        for service_name, service in self.services.items():
            progress[service_name] = service.progress()
        return progress

    def monitor_progress(self, show_progress=True, stop_event=None):
        with Progress(disable=not show_progress) as progress:
            tasks = {}
            for service_name, service in self.services.items():
                service_progress = service.progress()
                if service_progress["total"]:
                    tasks[service_name] = progress.add_task(f"[red]{service_name}", total=service_progress["total"])
            while tasks and not progress.finished:
                if stop_event is not None and stop_event.is_set():
                    break
                for task_name, task_id in tasks.items():
                    if progress._tasks[task_id].finished:
                        continue
                    p = self.services[task_name].progress()
                    description = None
                    if "framenumber" in p and p["elapsed_delta"]:
                        description = f"{task_name} {p['framenumber_delta'] / p['elapsed_delta']: 7.2f} fps"
                    progress.update(task_id, completed=p["elapsed"], description=description)
                time.sleep(1)


def _wait_for_run(runner, duration, show_progress=True):
    runner.monitor_progress(show_progress=show_progress)


def run(
    protocolfile,
    playlistfile=None,
    *,
    save_prefix=None,
    show_progress=True,
    debug=False,
    preview=False,
):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    runner = ResumableExperimentRunner(protocolfile=protocolfile, save_prefix_root=save_prefix)
    try:
        runner.setup_hardware()
        if preview:
            runner.prepare_run(save_prefix=save_prefix, preview=True)
            duration = 1_000_000
        elif playlistfile is None:
            runner.prepare_run(save_prefix=save_prefix)
            duration = runner.prot["maxduration"]
        else:
            analog_data_out, digital_data_out, duration = playlist_arrays(runner.prot, playlistfile)
            runner.prepare_run(
                save_prefix=save_prefix,
                analog_data_out=analog_data_out,
                digital_data_out=digital_data_out,
                duration=duration,
            )
        runner.start()
        if duration and duration > 0:
            _wait_for_run(runner, duration, show_progress=show_progress)
        return runner.stop_run()
    finally:
        runner.close()
