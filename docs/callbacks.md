# Callbacks
Each services loops over individual frames (camera) or chunks of data (DAQ) - callbacks process these. For services producing data at low rates and bandwidths, like temperature and humidity sensors being read out every couple of seconds, data can be logged to the service's log-file for simplicity.

## Usage in the service
- dict with friendly names and full class name
- protocol `callback`...
- event loop

## Anatomy of a callback (make you're own)
```
class CoolCallback(BaseCallback):
    pass
```