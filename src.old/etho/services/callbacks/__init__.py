# first define this and then import the submodules so callbacks are automatically
# registered by their name in the `callbacks` dict

callbacks = dict()


def _register_callback(func):
    """Adds func to model_dict Dict[modelname: modelfunc]. For selecting models by string."""
    if hasattr(func, "FRIENDLY_NAME"):
        callbacks[func.FRIENDLY_NAME] = func
    callbacks[func.__name__] = func
    return func


register_callback = _register_callback

from ._base import BaseCallback
from . import _image
from . import _trace
