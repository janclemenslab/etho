# Govee Temperature/Humidity Sensors

The `GOV` service supports Govee H5075 sensors over Bluetooth Low Energy (BLE).

## Discover the Sensor Address

On the acquisition computer, activate the `etho` conda environment and scan for
nearby sensors:

```powershell
conda activate etho
etho govee
```

After scanning for 10 seconds, the command lists each sensor's address, name,
temperature, and humidity. Match the temperature and humidity pair in a row to
the values shown on the physical sensor's display. If multiple sensors show
similar values, temporarily move or warm one sensor, run `etho govee` again,
and match the changed readings.

Copy the address from the matching row into the sensor's protocol block:

```yaml
GOV:
  address: AA:BB:CC:DD:EE:FF
  interval: 60
```

The `interval` is the logging interval in seconds.
