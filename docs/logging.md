# Logging
Information is logged using python's [logging module](https://docs.python.org/3/library/logging.html#logging-levels). Each services logs via to the head and (optionally) to a local file.

__logging broadcast to head:__ _Messages of level WARNING and above_ are broadcast to the head IP (129.168.1.1) on the `LOGGING_PORT` specified for each service and can be intercepted for display in console and logging to file via `ethomaster.head.headlogger`.

__logging to local file on node:__ _Messages of level INFO and above_ are logged to a local file on the node, if logger has been initialized via `self.init_local_logger(logfilename)`.