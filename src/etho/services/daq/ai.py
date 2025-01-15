# -*- coding: utf-8 -*-
import threading
import time
import numpy as np
import logging
from ..utils.log_exceptions import for_all_methods, log_exceptions
from typing import Optional, List

try:
    import PyDAQmx as daq
    from PyDAQmx.DAQmxCallBack import *
    from PyDAQmx.DAQmxConstants import *
    from PyDAQmx.DAQmxFunctions import *

    pydaqmx_import_error = None
except (ImportError, NotImplementedError) as pydaqmx_import_error:
    pass


logger = logging.getLogger(__name__)


@for_all_methods(log_exceptions(logger))
class AI(daq.Task):
    def __init__(
        self,
        dev_name="Dev1",
        cha_name=["ai0"],
        limits=None,
        rate=10000.0,
        nb_inputsamples_per_cycle=None,
        clock_source=None,
        terminals: Optional[List[str]] = None,
        logger=None,
    ):
        """[summary]

        Args:
            dev_name (str, optional): [description]. Defaults to "Dev1".
            cha_name (list, optional): [description]. Defaults to ["ai0"].
            limits (float, optional): [description]. Defaults to 10.0.
            rate (float, optional): [description]. Defaults to 10000.0.
            nb_inputsamples_per_cycle ([type], optional): [description]. Defaults to None.
            clock_source (str, optional): None for AI-synced clock.
                                          Use 'OnboardClock' for boards that don't support this (USB-DAQ).
                                          Defaults to None.
            terminals (List[str], optional):

        Raises:
            TypeError: [description]
            ValueError: [description]
        """
        if pydaqmx_import_error is not None:
            raise pydaqmx_import_error

        self.log = logger

        # check inputs
        super().__init__()
        if not isinstance(cha_name, (list, tuple)):
            raise TypeError(f"`cha_name` is {type(cha_name)}. Should be `list` or `tuple`")

        self.samples_read = daq.int32()

        self.cha_names = [dev_name + "/" + ch for ch in cha_name]  # append device name
        self.cha_string = ", ".join(self.cha_names)
        self.num_channels = len(cha_name)  # need to fix this if we want to use blocks "ai0:8"
        if nb_inputsamples_per_cycle is None:
            nb_inputsamples_per_cycle = int(rate)

        # terminals
        terminal_types = {
            "RSE": daq.DAQmx_Val_RSE,
            "NRSE": daq.DAQmx_Val_NRSE,
            "Diff": daq.DAQmx_Val_Diff,
            None: daq.DAQmx_Val_RSE,  # default
        }
        if terminals is None:  # default
            terminals = ["RSE" for _ in self.cha_names]
        elif len(terminals) != len(self.cha_names):
            raise ValueError("need term for each channel")
        self.cha_terminals = [terminal_types[terminal] for terminal in terminals]

        # limits
        if limits is None:  # default
            self.cha_limits = [[-10.0, 10.0] for _ in self.cha_names]
        elif isinstance(limits, (float, int)):  # single number
            self.cha_limits = [[-limits, limits] for _ in self.cha_names]
        else:
            self.cha_limits = limits

        if len(self.cha_limits) != len(self.cha_names) or not all([len(limit) == 2 for limit in self.cha_limits]):
            raise ValueError("need term for each channel")

        # FIX: input and output tasks can have different sizes
        self.callback = None
        self.data_rec = None  # called at end of callback

        # add all channels
        for name, terminal, limit in zip(self.cha_names, self.cha_terminals, self.cha_limits):
            self.CreateAIVoltageChan(
                name,
                "",
                terminal,
                limit[0],
                limit[1],
                daq.DAQmx_Val_Volts,
                None,
            )
        self.num_samples_per_chan = nb_inputsamples_per_cycle
        self.num_samples_per_event = nb_inputsamples_per_cycle  # self.num_samples_per_chan*self.num_channels
        self.AutoRegisterEveryNSamplesEvent(daq.DAQmx_Val_Acquired_Into_Buffer, self.num_samples_per_event, 0)
        self.CfgInputBuffer(self.num_samples_per_chan * self.num_channels * 4)

        self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.float64)  # init empty data array

        clock_source = "OnboardClock"  # use internal clock

        self.CfgSampClkTiming(
            clock_source,
            rate,
            daq.DAQmx_Val_Rising,
            daq.DAQmx_Val_ContSamps,
            self.num_samples_per_chan,
        )

        self.AutoRegisterDoneEvent(0)
        self._data_lock = threading.Lock()
        self._newdata_event = threading.Event()

    def __repr__(self):
        return "{0}: {1}".format(self.cha_type[0], self.cha_string)

    def stop(self):
        """Stop DAQ."""
        if self.data_rec is not None:
            for data_rec in self.data_rec:
                data_rec.send(None)
                data_rec.finish(verbose=True, sleepcycletimeout=2)
                data_rec.close()

    def EveryNCallback(self):
        """Call whenever there is data to be read from the buffer.

        Calls `self.data_rec` for processing data.
        """
        # for clean teardown, catch PyDAQmx.DAQmxFunctions.GenStoppedToPreventRegenOfOldSamplesError
        with self._data_lock:
            systemtime = time.time()
            self.ReadAnalogF64(
                daq.DAQmx_Val_Auto,
                1.0,
                daq.DAQmx_Val_GroupByScanNumber,
                self._data,
                self.num_samples_per_chan * self.num_channels,
                daq.byref(self.samples_read),
                None,
            )
            # only keep samples that were actually read, .value converts c_long to int
            self._data = self._data[: self.samples_read.value, :]

            if self.data_rec is not None:
                for data_rec in self.data_rec:
                    if self._data is not None:
                        self.log.warning(f"{data_rec} {systemtime}")
                        data_rec.send((self._data, systemtime))
            self._newdata_event.set()

        return 0  # The function should return an integer

    def DoneCallback(self, status):
        """Call when Task is stopped/done."""
        self.log.warning("Done status", status)
        return 0  # The function should return an integer
