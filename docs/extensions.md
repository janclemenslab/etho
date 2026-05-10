(extensions)=
# Extensions

Etho has two main extension points:

- **Callbacks** process data that an existing service already produces.
- **Services** add a new hardware controller or long-running process.

Use a callback when the `GCM`, `DAQ`, or `DLP` service already gives you the
data stream you need. Add a service when new hardware needs its own setup,
start, stop, logging, and progress lifecycle.

## Adding A Callback

Callbacks are registered in `etho.services.callbacks.callbacks`. Services look
up protocol callback names in that registry and launch each callback in a
separate concurrent task.

1. Add a callback class under `src/etho/services/callbacks/`.
2. Subclass `BaseCallback`.
3. Decorate the class with `@register_callback`.
4. Set `FRIENDLY_NAME` to the protocol-facing name.
5. Implement `_loop(self, data)`.
6. Implement `_cleanup(self)` if the callback opens files, hardware, windows, or
   buffers. Call `super()._cleanup()` at the end.
7. If the class lives in a new module, import that module from
   `src/etho/services/callbacks/__init__.py` so registration happens at import
   time.

```python
from etho.services.callbacks import register_callback
from etho.services.callbacks._base import BaseCallback


@register_callback
class SaveSummary(BaseCallback):
    FRIENDLY_NAME = "save_summary"

    def __init__(self, data_source, file_name, rate=0, **kwargs):
        super().__init__(data_source, rate=rate)
        self.file_name = file_name

    def _loop(self, data):
        payload, timestamps = data
        ...

    def _cleanup(self):
        ...
        super()._cleanup()
```

Use the friendly name in the service block:

```yaml
GCM:
  callbacks:
    save_summary:
      rate: 0.5
```

Callback constructor arguments come from two places:

- The service supplies common arguments such as `file_name`, frame dimensions,
  frame rate, DAQ channel metadata, or input chunk size.
- The protocol supplies callback-specific options under the callback name.

Camera callbacks usually receive `(image, (system_ts, image_ts))`. Timestamp
callbacks receive timestamp data without the image payload. DAQ callbacks receive
analog input chunks and metadata from the analog input task.

## Adding A Service

New services should follow `src/etho/services/TemplateZeroService.py`. A service
subclasses `BaseZeroService`, exposes a ZeroRPC server, and implements the same
lifecycle used by the built-in services.

1. Copy `TemplateZeroService.py` to
   `src/etho/services/<NAME>ZeroService.py`.
2. Rename the class to a short uppercase service name, such as `TMP`.
3. Set unique `LOGGING_PORT` and `SERVICE_PORT` values. Existing services use
   logging ports in the `1420-1460` range and service ports beginning with
   `42`; the last two digits normally match.
4. Set `SERVICE_NAME` to the class name.
5. Implement `setup_client(...)` for protocol-to-service wiring. This is where
   the service reads its protocol block, assigns its default port, calls
   `make(...)`, calls the remote `setup(...)`, and initializes the local logger.
6. Implement `setup(...)` for hardware allocation, run configuration, worker
   thread setup, and `self.info`.
7. Implement `start()` to start workers, hardware acquisition, timers, and
   callbacks.
8. Implement `finish(stop_service=False)` to stop timers, signal workers, close
   hardware, close callbacks, and optionally call `service_stop()`.
9. Implement `is_busy()`, `test()`, and `cleanup()`.
10. Keep the module-level `cli()` and `if __name__ == "__main__"` block so
   `BaseZeroService.make(...)` can launch the service with `python -m`.

The template shows the expected structure:

```python
from . import register_service
from .ZeroService import BaseZeroService
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@register_service
class TMP(BaseZeroService):
    LOGGING_PORT = 1443
    SERVICE_PORT = 4243
    SERVICE_NAME = "TMP"
    CLIENT_START_GROUP = "pre"

    @classmethod
    def setup_client(cls, service_key, service_index, prot, defaults,
                     playlistfile, save_prefix, preview, new_console):
        ...

    def setup(self, duration):
        self.duration = float(duration)
        ...

    def start(self):
        ...

    def finish(self, stop_service=False):
        ...

    def is_busy(self):
        ...

    def test(self):
        ...

    def cleanup(self):
        ...
```

Services that run continuously should do the work in a thread or hardware task
created during `setup()` and started during `start()`. Use a `threading.Event`
or equivalent stop signal so `finish()` can stop the worker cleanly.

## Wiring A Service Into Experiments

`etho run` looks up services in `etho.services.SERVICE_REGISTRY` by their
`SERVICE_NAME`. Suffixed protocol names such as `GCM2` resolve to `GCM`. Do not
edit `src/etho/client.py` for a new service; register the service class with
`@register_service` and import the service from `src/etho/services/__init__.py`
so the decorator runs.

`setup_client(...)` receives the protocol, global defaults, playlist path,
`save_prefix`, preview flag, and debug console flag. It should return the
configured remote service client, or `None` when the service should be skipped
for that run.

Set `CLIENT_START_GROUP` only when start order matters:

- `pre`: default; starts before trigger and DAQ services.
- `trigger`: starts after `pre` services.
- `daq`: starts after `pre` and `trigger` services, with the existing startup
  delay.

Minimal protocol shape:

```yaml
maxduration: 30
use_services: [TMP]

TMP:
  duration: 30
  port: 4243
```

The exact service block should match what the new service's `setup_client(...)`
passes into its remote `setup(...)` call.

## Documentation And Tests

When adding a public extension, update the matching docs:

- Callback options belong in `docs/callbacks.md` and protocol examples.
- Service configuration belongs in `docs/configuration/protocol.md`.
- Hardware-specific behavior belongs under `docs/hardware/`.
- API pages are automatically generated.

For services, add tests around the client wiring and any non-hardware parsing or
state handling. For callbacks, test constructor options and `_loop()` behavior
without requiring real hardware when possible.
