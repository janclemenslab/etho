import defopt
import logging
import platform
import importlib

from .call import client

logger = logging.getLogger(__name__)


def version(*, debug: bool = False):
    """Displays system, version, and hardware info.

    Args:
        debug (bool): Display exception info for failed imports. Defaults to False.
    """
    import etho
    import sys
    import pandas as pd
    import numpy as np
    import scipy
    import h5py

    try:
        import pyqtgraph
        import qtpy

        has_gui = True
    except (ImportError, ModuleNotFoundError):
        has_gui = False

    logger.info(f"{platform.platform()}")
    logger.info(f"etho v{etho.__version__}")
    logger.info("")
    logger.info("  LIBRARY VERSIONS")
    logger.info(f"    python v{sys.version}")
    logger.info(f"    pandas v{pd.__version__}")
    logger.info(f"    numpy v{np.__version__}")
    logger.info(f"    h5py v{h5py.__version__}")
    logger.info(f"    scipy v{scipy.__version__}")
    logger.info("")
    logger.info("  GUI SUPPORT")
    logger.info(f"     GUI is {'' if has_gui else 'not'}available.")
    if has_gui:
        logger.info(f"     pyqtgraph v{pyqtgraph.__version__}")
        logger.info(f"     {qtpy.API_NAME} v{qtpy.PYQT_VERSION or qtpy.PYSIDE_VERSION}")
        logger.info(f"     Qt v{qtpy.QT_VERSION}")
        logger.info(f"     qtpy v{qtpy.__version__}")

    logger.info("")
    logger.info("  HARDWARE SUPPORT")

    libs = {
        "Spinnaker camera SDK": "PySpin",
        "FlyCapture camera SDK": "PyCapture2",
        "Ximea camera SDK": "ximea",
        "DCAM (Hamamatsu) camera SDK": "pylablib",
        "NI daqmx": "pydaqmx",
        "Lightcrafter projector": "pycrafter4500",
    }
    for lib_name, lib_import in libs.items():
        try:
            importlib.import_module(lib_import)
            logger.info(f"     {lib_name} ({lib_import}) is available")
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"     {lib_name} ({lib_import}) is NOT available.")
            if debug:
                logger.exception("     DEBUG info", exc_info=e)


def no_gui():
    """Could not import the GUI. For instructions on how to install the GUI, check the docs janclemenslab.org/etho/install.html."""
    logger.warning("Could not import the GUI.")
    logger.warning("For instructions on how to install the GUI,")
    logger.warning("check the docs janclemenslab.org/etho/install.html.")


def main():
    """Command line interface for DAS."""
    subcommands = {
        "call": client.client,
        "version": version,
    }

    try:
        from .gui import app
        subcommands["gui"] = app.main
    except (ImportError, ModuleNotFoundError):
        logging.exception("No GUI avalaible.")
        # fall back to function that displays helpful instructions
        subcommands["gui"] = no_gui

    logging.basicConfig(level=logging.INFO, force=True)
    defopt.run(subcommands, show_defaults=False)
