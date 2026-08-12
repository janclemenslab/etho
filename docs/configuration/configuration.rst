
.. _configuration-overview:

Configuration
=============

Etho uses configuration files so common rig settings, experiment settings, and
trial-level stimulus definitions can be changed without editing Python code.
Each file type has a specific role:

- `A global configuration <global.html>`__ file controls global hardware setting - e.g. user names, folder names etc.
- `Experiment protocols <protocol.html>`__ files control hardware settings on a per-experiment basis - e.g. allow to set sampling rate or frame size
- `Stimulus playlists <playlist.html>`__ files control experiment flows - e.g. they allow to define a set of sounds to be played


.. toctree::
   :maxdepth: 1
   :hidden:

   global
   protocol
   playlist
   calibration_speaker
   calibration_led
