Installation and initialization
===============================

Etho is a Python package with optional hardware SDK dependencies.
Etho is tested for Windows acquisition rigs. The hardware stack depends on
vendor SDKs, which may also work on macOS or Linux but have not been tested
with ``etho``. The install and run commands in the user documentation are
therefore Windows PowerShell commands. macOS and Linux can be used for
development, tests, and documentation work that does not require hardware SDKs.

Create a named conda environment, activate it, and install ``etho`` with
``uv pip``:

.. code-block:: powershell

   conda create -n etho -c conda-forge -y python=3.14 uv pip git
   conda activate etho
   uv pip install etho-python
   etho init

``etho`` supports Python 3.10 through 3.14. The Python version to use depends
on the hardware SDKs required by the rig. Check the Python versions supported
by the required hardware SDKs before installation.


Optional Hardware Packages
--------------------------

Install only the packages and vendor drivers required by the Windows rig:

- Ximea cameras: Install the Ximea driver and Python package from Ximea.
- FLIR/Spinnaker cameras: install the Spinnaker SDK and the matching PySpin Python package from FLIR. Public downloads only list Python 3.10, but FLIR support can provide Python 3.14 bindings.
- Basler cameras: install Basler pylon and ``pypylon``.
- Hamamatsu DCAM cameras: install the DCAM driver and ``pylablib``.
- National Instruments DAQ: install NI-DAQmx. ``pydaqmx`` is installed by default.
- LightCrafter/DLP projector rigs: install the projector control software and ``pycrafter4500``.
- Video writing through VidGear: install ``vidgear[core]`` if the protocol uses VidGear callbacks.

After installing optional SDKs, run:

.. code-block:: powershell

   etho version

Missing optional hardware entries are expected on machines that do not operate
that hardware.

Initialize the config files and folders
---------------------------------------

If the environment already exists, activate it before initializing config files
and folders:

.. code-block:: powershell

   conda activate etho
   etho init


On Windows this creates ``C:\Users\<user>\data`` for saved runs and
``C:\Users\<user>\ethoconfig`` with:

- ``ethoconfig.yml`` for :doc:`global configuration <configuration/global>`
- ``playlists/`` for :doc:`stimulation playlists <configuration/playlist>`
- ``protocols/`` for :doc:`experimental protocols <configuration/protocol>`
- ``stim/`` for stimulus files such as WAV files
