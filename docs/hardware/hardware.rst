
.. _hardware-overview:

Supported Hardware
==================

Etho separates experiment control into services. The pages in this section
describe the rig-facing hardware assumptions for the services that are commonly
operated from protocols: cameras, National Instruments DAQ devices, DLP
projectors, and ScanImage trigger integration.

You can add support for new hardware by implementing the appropriate service interface. See :ref:`extensions`.


.. toctree::
   :maxdepth: 1
   :hidden:

   camera
   nidaq
   projector
   scanimage
