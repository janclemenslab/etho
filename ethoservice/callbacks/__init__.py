# first define this and then import the submodules so callbacks are automatically
# registered by their name in the `callbacks` dict
callbacks = dict()
def _register_callback(func):
    """Adds func to model_dict Dict[modelname: modelfunc]. For selecting models by string."""
    callbacks[func.__name__] = func
    return func

from . import _trace
from . import _image