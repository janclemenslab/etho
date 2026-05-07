# Logging

Etho services use Python's `logging` module. Logs are emitted in two places:
network logs for live status display and service-local files for experiment
records.

## Network Logs

Each service publishes log messages on its `LOGGING_PORT`. The message prefix
includes timestamp, service name, and host name.

Network logging is useful for live monitoring, but it should not be treated as
the only experiment record. Always inspect the service-local log files after a
rig validation run.

## Local Log Files

During normal `etho run` execution, services initialize local log files under:

```text
<savefolder>/<save-prefix>/
```

Common examples:

- `<save-prefix>_gcm.log`
- `<save-prefix>_daq.log`
- `<save-prefix>_gov.log`

Local logs record service setup, runtime status, callback initialization, and
cleanup messages. They are the first place to check when saved data is missing,
frame rates differ from the protocol, or a hardware SDK import fails.

## Debugging

Use:

```shell
etho version --debug
etho run protocol.yml playlist.txt --debug
```

`etho version --debug` prints exception details for optional hardware imports.
`etho run --debug` starts services with more verbose logging and new consoles
where supported by the platform.
