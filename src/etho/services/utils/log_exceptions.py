import logging


def for_all_methods(decorator):
    """ "Decorates all methods of a class with 'decorator'."""

    def decorate(cls):
        for attr in cls.__dict__:  # there's propably a better way to do this
            if callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls

    return decorate


def log_exceptions(logger=None):
    """
    A decorator that wraps the passed in function and logs
    exceptions should one occur

    @param logger (optional): The logging object
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                # log the exception
                err = f"Exception in {func.__name__}: "
                logger.exception(err)
                # re-raise the exception
                raise

        return wrapper

    return decorator
