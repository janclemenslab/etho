
.. _hardware-overview:

Supported Hardware
==================

Etho separates experiment control into services. The pages in this section
describe the rig-facing hardware assumptions for the services that are commonly
operated from protocols:

- :doc:`Cameras <camera>`
- :doc:`NI daq <nidaq>`
- :doc:`DLP projectors <projector>`
- :doc:`ScanImage microscopes <scanimage>`

You can add support for new hardware by implementing the appropriate service interface. See :ref:`extensions`.


.. toctree::
   :maxdepth: 1
   :hidden:

   camera
   nidaq
   projector
   scanimage
