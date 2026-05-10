.. etho documentation master file, created by
   sphinx-quickstart on Mon Aug 16 20:53:49 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Etho: A Python framework for coordinating stimuli, data acquisition, and hardware control in neuroscience experiments
=====================================

Etho runs behavioral experiments by coordinating cameras, data acquisition,
projectors, sensors, playlists, callbacks, and saved outputs from a single
Python command-line or GUI entry point.

.. grid:: 2

    .. grid-item-card::  Hardware support
        :link: hardware/hardware
        :link-type: doc

        Etho supports cameras, data acquisition devices, projectors, and sensors
        from multiple vendors.

    .. grid-item-card::  Text-based configuration
         :link: configuration/configuration
         :link-type: doc

         Etho uses YAML configuration files for rig and experiment settings, and
         supports dynamic configuration changes during runtime.

    .. grid-item-card:: Realtime
         :link: logging
         :link-type: doc

         Etho supports realtime logging of video and audio data, with flexible
         configuration of what data to log and how to save it.

    .. grid-item-card:: Fast & parallel

         Etho executes hardware services and logging callbacks in parallel, making use of multi-core and GPU hardware.

    .. grid-item-card:: Terminal and graphical user interfaces
         :link: cli
         :link-type: doc

         Etho provides a terminal interface and a GUI for configuring, monitoring, and controlling experiments.

    .. grid-item-card:: Modular & extensible
         :link: extensions
         :link-type: doc

         Etho is designed to be easily extended with new hardware support and callbacks.


.. toctree::
   :maxdepth: 2
   :glob:
   :hidden:

   Home <self>
   Installation <install>
   Tutorial <tutorial>
   Configuration <configuration/configuration>
   Logging <logging>
   Callbacks <callbacks>
   Extensions <extensions>
   Hardware <hardware/hardware>
   CLI <cli>
   API <api_etho>

