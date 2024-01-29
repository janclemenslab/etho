import defopt
import logging
import platform
import importlib
import yaml
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from .call import client
except Exception as e:
    logging.error(e)
    client = None

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


def init():
    """Initializes config files and folders."""
    home = Path.home()

    cfg = {'GENERAL': {'user': 'ncb', 'folder': str(home), 'save_directory': str(home / 'data')},
           'HEAD': {},
           'ATTENUATION': {-1: 1,  0: 1,100: 1,150: 1, 200: 1, 250: 1, 300: 1, 350: 1, 400: 1, 450: 1, 500: 1, 600: 1, 700: 1, 800: 1, 900: 1, 1000: 1, 1500: 1, 2000: 1},
          }

    paths = {'playlistfolder': 'ethoconfig/playlists',
            'protocolfolder': 'ethoconfig/protocols',
            'stimfolder': 'ethoconfig/stim',
            'datafolder': 'data'}
    logging.info('Creating default directories:')
    for name, path in paths.items():
        logging.info('   ' + path)
        p = home / Path(path)
        p.mkdir(parents=True, exist_ok=True)
        cfg['HEAD'][name] = str(p)

    logging.info(cfg)

    path_cfg = home / 'ethoconfig.yml'
    if path_cfg.exists():
        logging.info(f'The configuration file {str(path_cfg)} exists. Will not overwrite. You may have to update the file manually')
    else:
        logging.info(f'Writing configuration to {str(path_cfg)}.')
        with open(path_cfg, mode='w') as f:
            yaml.dump(cfg, f, Dumper=yaml.SafeDumper)

    logging.info('Generating test files:')
    # generate test protocol
    protocol = {'NODE': {'maxduration': 30, 'use_services': ['GCM']},
            'GCM': {'frame_rate': 30,
            'frame_width': 320,
            'frame_height': 240,
            'frame_offx': 0,
            'frame_offy': 0,
            'shutter_speed': 1.0,
            'brightness': 1.0,
            'gamma': 1.0,
            'gain': 1.0,
            'cam_serialnumber': 42,
            'cam_type': 'Dummy',
            'callbacks': {'disp': {'framerate': 10}}}}
    path_protocol = home / 'ethoconfig/protocols/dummy_1min.yml'
    logging.info(f'   protocol {str(path_protocol)}.')

    with open(path_protocol, mode='w') as f:
            yaml.dump(protocol, f, Dumper=yaml.SafeDumper)

    # generate test playlist
    playlist = {'stimFileName': {0: 'SIN_100_0_1000'},
                'silencePre': {0: 10000},
                'silencePost': {0: 9000},
                'delayPost': {0: 0},
                'intensity': {0: 0.0},
                'freq': {0: 100},
                'MODE': {0: None}}
    path_playlist = home / 'ethoconfig/playlists/0_silence.txt'
    logging.info(f'   playlist {str(path_playlist)}.')
    pd.DataFrame.from_dict(playlist).to_csv(path_playlist, sep='\t', index=False)


def main():
    """Command line interface for DAS."""
    subcommands = {
        "version": version,
        "init": init,
    }

    if client is not None:
        subcommands.update({"call": client.client})

    try:
        from .gui import app
        subcommands["gui"] = app.main
    except (ImportError, ModuleNotFoundError):
        logging.exception("No GUI avalaible.")
        # fall back to function that displays helpful instructions
        subcommands["gui"] = no_gui

    logging.basicConfig(level=logging.INFO, force=True)
    defopt.run(subcommands, show_defaults=False)
