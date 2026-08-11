
.. _hardware-overview:

Supported Hardware
==================

Etho separates experiment control into services. The pages in this section
describe the rig-facing hardware assumptions for the services that are commonly
operated from protocols:

- :doc:`Cameras (FLIR, Basler, Ximea, Hamamatsu) <camera>`
- :doc:`National Instruments DAQmx compatible devices <nidaq>`
- :doc:`DLP projectors <projector>`
- :doc:`ScanImage microscopes <scanimage>`
- :doc:`Govee H5075 temperature/humidity sensors <govee>`

You can add support for new hardware by implementing the appropriate service interface. See :ref:`extensions`.


.. toctree::
   :maxdepth: 1
   :hidden:

   camera
   nidaq
   projector
   scanimage
   govee
