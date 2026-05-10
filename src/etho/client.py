import time
import logging
from rich.progress import Progress
import rich
import threading
import _thread as thread
import queue
from typing import Optional, Union, Dict, Any
import psutil

from .utils.tui import rich_information

from . import config
from . import services as service_module
from .utils.config import defaultify, readconfig


def timed(fn, s, *args, **kwargs):
    quit_fun = thread.interrupt_main  # raises KeyboardInterrupt
    timer = threading.Timer(s, quit_fun)
    timer.start()
    try:
        result = fn(*args, **kwargs)
    except:  # catch KeyboardInterrupt for silent timeouts
        result = 1
    finally:
        timer.cancel()
    return result


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


def _reject_remote_host_blocks(prot: Dict[str, Any]) -> None:
    remote_services = []
    for service_name in prot["use_services"]:
        service_config = prot.get(service_name, {})
        if isinstance(service_config, dict) and "host" in service_config:
            remote_services.append(service_name)
    if remote_services:
        services = ", ".join(remote_services)
        raise ValueError(f"Remote service hosts are no longer supported. Remove the 'host' block from: {services}.")


def _setup_services(prot, defaults, playlistfile, save_prefix, preview, new_console):
    services = {}
    service_classes = {}
    service_counts = {}

    for service_name in prot["use_services"]:
        service_class = service_module.service_class_for(service_name)
        service_type = service_class.SERVICE_NAME
        service_index = service_counts.get(service_type, 0)
        service_counts[service_type] = service_index + 1

        service = service_class.setup_client(
            service_name,
            service_index,
            prot,
            defaults,
            playlistfile,
            save_prefix,
            preview,
            new_console,
        )
        if service is None:
            continue

        services[service_name] = service
        service_classes[service_name] = service_class

    return services, service_classes


def _start_services(services, service_classes):
    logging.info("Starting services")

    start_groups = {service_name: getattr(service_classes[service_name], "CLIENT_START_GROUP", "pre") for service_name in services}
    started_groups = set()
    time_last_prereq_started = time.time()

    def start_group(group):
        nonlocal time_last_prereq_started
        started_groups.add(group)
        for service_name, service in services.items():
            if start_groups[service_name] != group:
                continue
            logging.info(f"   {service_name}.")
            service.start()
            if group in {"pre", "trigger"}:
                time_last_prereq_started = time.time()

    start_group("pre")
    time.sleep(0.5)
    start_group("trigger")

    if "daq" in start_groups.values():
        wait_remaining = 5 - (time.time() - time_last_prereq_started)
        if wait_remaining > 0:
            time.sleep(wait_remaining)
    start_group("daq")

    for group in start_groups.values():
        if group not in started_groups:
            start_group(group)

    logging.info("All services started.")


def client(
    protocolfile: Optional[str],
    playlistfile: Optional[str] = None,
    *,
    protocol: Optional[Dict[str, Any]] = None,
    save_prefix: Optional[str] = None,
    show_progress: bool = True,
    monitor: bool = False,
    debug: bool = False,
    preview: bool = False,
    _stop_event: Optional[threading.Event] = None,
    _done_event: Optional[threading.Event] = None,
    _queue: Optional[queue.Queue] = None,
):
    """Starts an experiment.

    Args:
        protocolfile (Optional[str]): Path to the protocol file.
        playlistfile (Optional[str]): _description_.
        protocol (Optional[Dict[str, Any]]): Protocol parameters provided directly by the GUI.
        save_prefix (Optional[str]): Specify the stem of the filename for all saved data and logs. Will defaults to HOSTNAME-YYYYMMDD_hhmmss, where HOSTNAME is the computer name the service is run on (typically localhost).
        show_progress (bool): Show a progress bar. Disable if performance is criticial.
        monitor (bool): Keep the run in the progress/cleanup loop even when the progress display is hidden.
        debug (bool): More verbose logs.
        preview (bool): Preview the camera (will disable saving and logging and only open a window with the camera view).
        _stop_event (threading.Event, optional): Used to stop the task from an outside thread. Defaults to None.
        _done_event (threading.Event, optional): Set to signal that the task is done/stopped to an outside thread. Defaults to None.
        _queue (queue.Queue, optional): Signal the expected duration of the task to outside funs. Defaults to None.
    """

    # load config/protocols
    if protocol is not None:
        prot = defaultify(protocol)
    else:
        prot = readconfig(protocolfile)
    logging.debug(prot)
    defaults = config
    if defaults["host"] is None:
        defaults["host"] = "localhost"
    if defaults["python_exe"] is None:
        defaults["python_exe"] = "python"
    if defaults["serializer"] is None:
        defaults["serializer"] = "pickle"
    _reject_remote_host_blocks(prot)

    rich.print(defaults)
    # unique file name for video and node-local logs
    if save_prefix is None:
        save_prefix = f"{defaults['host']}-{time.strftime('%Y%m%d_%H%M%S')}"
    logging.info(f"Saving as {save_prefix}.")

    new_console = debug

    services, service_classes = _setup_services(prot, defaults, playlistfile, save_prefix, preview, new_console)

    # display config info
    for key, s in services.items():
        rich_information(s.information(), prefix=key)

    _start_services(services, service_classes)

    if monitor or show_progress:
        total = 0
        for service_name, service in services.items():
            total = max(total, service.progress()["total"])
        if _queue is not None:
            _queue.put(total)
        cli_progress(services, save_prefix, _stop_event, _done_event, show_progress=show_progress)
    else:
        return services


def cli_progress(
    services: Dict[str, Any],
    save_prefix: str,
    stop_event: Optional[threading.Event] = None,
    done_event: Optional[threading.Event] = None,
    show_progress: bool = True,
):
    """_summary_

    Args:
        services (_type_): Dictionary of intialized services.
        save_prefix (_type_): Name of the expt.
        stop_event (_type_, optional): Used to stop the task from an outside thread. Defaults to None.
        done_event (_type_, optional): Set to signal that the task is done/stopped to an outside thread. Defaults to None.
    """
    STOPPED_PREMATURELY = False
    try:
        with Progress(disable=not show_progress) as progress:
            tasks = {}
            for service_name, service in services.items():
                tasks[service_name] = progress.add_task(f"[red]{service_name}", total=service.progress()["total"])
            RUN = True
            while RUN and not progress.finished:
                for task_name, task_id in tasks.items():
                    if stop_event is not None and stop_event.is_set():
                        break
                    if progress._tasks[task_id].finished:
                        continue
                    try:
                        p = timed(services[task_name].progress, 5)
                        description = None
                        if "framenumber" in p:
                            description = f"{task_name} {p['framenumber_delta'] / p['elapsed_delta']: 7.2f} fps"
                        progress.update(task_id, completed=p["elapsed"], description=description)
                    except:  # if call times out, stop progress display - this will stop the display whenever a task times out - not necessarily when a task is done
                        progress.stop_task(task_id)
                time.sleep(1)

                if stop_event is not None and stop_event.is_set():
                    logging.info("Received STOP signal. Cancelling jobs:")
                    for task_name, task_id in tasks.items():
                        progress.stop_task(task_id)
                    RUN = False
                    STOPPED_PREMATURELY = True
        time.sleep(1)
        if STOPPED_PREMATURELY:
            logging.info("Finishing jobs.")
            for service_name, service in services.items():
                logging.info(f"   {service_name}")
                try:
                    service.finish()
                except Exception as e:
                    logging.warning("     Failed.")
                    print(e)
                logging.info("       done.")

        time.sleep(4)
    finally:
        logging.info("Cleaning up jobs.")
        kill_child_processes()
        if done_event is not None:
            done_event.set()
        logging.info(f"Done with experiment {save_prefix}.")
