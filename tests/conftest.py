"""Pytest configuration and fixtures."""


def has_daq_hardware():
    """Check if PyDAQmx hardware is available."""
    try:
        from etho.services.daq.IOTask import IOTask
        return True
    except (ImportError, NameError, NotImplementedError):
        return False
