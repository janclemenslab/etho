# Logging

Etho services use Python's `logging` module. Logs are emitted in two places:
- _Terminal logs_ for live status display
- _Log files_ for experiment records.

## Terminal Logs

Each service publishes log messages on its `LOGGING_PORT`. The message prefix
includes timestamp, service name, and host name.

Network logging is useful for live monitoring and debugging. It is hidden by
default but can be enabled in the GUI with the debug checkbox, or from
PowerShell using the `--debug` flag:

```powershell
etho run ".\protocol.yml" ".\playlist.txt" --debug
```

In debug mode, one terminal window is opened per service to display its log
messages.


## Log Files

During normal `etho run` execution, services initialize local log files under:

```text
<savefolder>\<save-prefix>\
```

Common examples:

- `<save-prefix>_gcm.log`
- `<save-prefix>_daq.log`
- `<save-prefix>_gov.log`

Local logs record service setup, runtime status, callback initialization, and
cleanup messages. They are the first place to check when saved data is missing,
frame rates differ from the protocol, or a hardware SDK import fails.

