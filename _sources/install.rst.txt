Installation and initialization
===============================

Etho is a Python package with optional hardware SDK dependencies.
You can install it using uv or conda, and then initialize the config files and folders.

.. tabs::

   .. group-tab:: :iconify:`material-icon-theme:uv` uv (recommended)

         .. code-block:: bash

            uv venv --python 3.14
            .venv\Scripts\activate
            uv pip install etho-python

   .. group-tab:: :iconify:`vscode-icons:file-type-conda` conda

      Use this environment if you need vendor camera SDKs that have only been validated on Python 3.10.
      Use conda for the base environment and ``uv pip install`` for non-conda Python packages.
      .. code-block:: bash

         conda create -n etho -c conda-forge -y \
         python=3.10 "numpy<2" scipy h5py opencv pandas pyzmq gevent future \
         pillow msgpack-python pyyaml ipython uv pip git defopt msgpack-numpy \
         rich psutil pydaqmx pyqtgraph qtpy pyside6-essentials zarr
         conda activate etho
         uv pip install zerorpc-numpy etho-python --no-deps

      The ``--no-deps`` install keeps conda-owned packages in control and only
      installs the packages that are not available from the conda command above.


Optional Hardware Packages
--------------------------

Install only the packages and vendor drivers required by the rig:

- Ximea cameras: install the Ximea driver and Python package from Ximea.
- FLIR/Spinnaker cameras: install the Spinnaker SDK and the matching PySpin Python package from FLIR.
- Basler cameras: install Basler pylon and ``pypylon``.
- Hamamatsu DCAM cameras: install the DCAM driver and ``pylablib``.
- National Instruments DAQ: install NI-DAQmx. ``pydaqmx`` is installed by default.
- LightCrafter/DLP projector rigs: install the projector control software  and ``pycrafter4500``.
- Video writing through VidGear: install ``vidgear[core]`` if the protocol uses VidGear callbacks.

After installing optional SDKs, run:

.. code-block:: bash

   etho version

Missing optional hardware entries are expected on machines that do not operate
that hardware.

Initialize the config files and folders
---------------------------------------

Activate the environment and initialize config files and folders:

.. tabs::

   .. group-tab:: :iconify:`material-icon-theme:uv` uv (recommended)

         .. code-block:: bash

            .venv\Scripts\activate
            etho init

   .. group-tab:: :iconify:`vscode-icons:file-type-conda` conda

      .. code-block:: bash

         conda activate etho
         etho init


This creates ``~/data`` for saved runs and ``~/ethoconfig`` with:

- ``ethoconfig.yml`` for :doc:`global configuration <configuration/global>`
- ``playlists/`` for :doc:`stimulation playlists <configuration/playlist>`
- ``protocols/`` for :doc:`experimental protocols <configuration/protocol>`
- ``stim/`` for stimulus files such as WAV files
