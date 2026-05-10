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
5. Implement `setup(...)` for hardware allocation, run configuration, worker
   thread setup, and `self.info`.
6. Implement `start()` to start workers, hardware acquisition, timers, and
   callbacks.
7. Implement `finish(stop_service=False)` to stop timers, signal workers, close
   hardware, close callbacks, and optionally call `service_stop()`.
8. Implement `is_busy()`, `test()`, and `cleanup()`.
9. Keep the module-level `cli()` and `if __name__ == "__main__"` block so
   `BaseZeroService.make(...)` can launch the service with `python -m`.

The template shows the expected structure:

```python
from .ZeroService import BaseZeroService
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class TMP(BaseZeroService):
    LOGGING_PORT = 1443
    SERVICE_PORT = 4243
    SERVICE_NAME = "TMP"

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

A service module is not enough for `etho run` by itself. The experiment client
must know how to construct it from a protocol.

1. Import the service class in `src/etho/client.py`.
2. Add a client branch that recognizes the protocol service name or prefix in
   `use_services`.
3. Merge global defaults with the service block.
4. Assign a default port when the protocol does not provide one.
5. Call `<SERVICE>.make(...)`.
6. Call `setup(...)` with arguments from the protocol.
7. Initialize the local logger with `init_local_logger(...)`.
8. Store the service in the `services` dictionary.
9. Start it in the correct order relative to cameras, triggers, DAQ output, and
   other hardware.
10. Add protocol documentation and a focused test that proves the client wires
    the new service correctly.

Minimal protocol shape:

```yaml
maxduration: 30
use_services: [TMP]

TMP:
  duration: 30
  port: 4243
```

The exact service block should match the new service's `setup(...)` signature
and any runtime options it needs.

## Documentation And Tests

When adding a public extension, update the matching docs:

- Callback options belong in `docs/callbacks.md` and protocol examples.
- Service configuration belongs in `docs/configuration/protocol.md`.
- Hardware-specific behavior belongs under `docs/hardware/`.
- API pages are automatically generated.

For services, add tests around the client wiring and any non-hardware parsing or
state handling. For callbacks, test constructor options and `_loop()` behavior
without requiring real hardware when possible.
