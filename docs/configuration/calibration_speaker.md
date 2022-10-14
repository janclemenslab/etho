# Speaker calibration
Goal is to set the attenuation data in `ethoconfig.yml` such that a value of 1 corresponds to the correct unit.

...

The microphone is calibrated on 08/04/2019. The data is in a `yml` file in the server under ukme04>#Data>playback>calibration>mic_calibration folder

## Setup the hardware
Place mic roughly were the fly would be in the rig using the micromanipulator.
Measure the distance to the center of the speaker (normally 10cm).
Connect the mic to the amp box (channel A).
Connect the amp's BNC out with an analog input (ai0) on the National Instruments break out box.
Power the amp with the lab power supply.

## Set up and run the software
1. Go to Documents>calibration in the recording PC.
2. Double click on `playback_calibration.task` file to run it.
Be sure that:
 - Channel is `ai0` (i.e. the analog input the amp's output is connected to)
 - Type is `Differential`
 - Under the Task tab, Desired Sample Rate is `10000`
3. Start the playback software, select the rpi, select playlist `test_calibration.txt` and protocol `calibration`.
4. Start playback, start recording on DAQexpress. Try not to miss the beginning of the stimulus.
5. When the playlist is finished, stop the recording in DAQexpress and export the data as a csv file. The csv file name should **include the box name** (e.g. rpi7.csv). The file should be saved under ukme04>#Data>playback>calibration>**[date-of-recording]** folder
6. Copy the **ethoconfig.yml** file from the recording PC (recording usually uses C:/Users/ncb/ethoconfig.yml) to ukme04>#Data>playback>calibration>**[date-of-recording]** folder and change its name according to the recording.

## Analyze the results
1. Open `playback_calibration.ipynb` and give inputs for `recording_name`, `config_file_name`.
2. The stimulus on/offsets are defined manually by cutting the silent part of the recording by `cut` value and specifying the time point `s0` that coincides with the first stimulus onset
3. Run the whole file to calculate the new attenuation values printed at the end of the notebook.

 - *Graphs are saved under ukme04>#Data>playback>calibration>**[date-of-recording]**>figs folder.*
 - *It is good practice to re-run the calibration for testing that everything is correctly calibrated.*

**Example file hierarchy/naming**

Listing every file needed for analysis. All data from the calibration is inside 20200818 folder. After analysis, there will be a `figs` folder created under 20200818 folder.

```bash
playback
├────── calibration
│        ├── mic_calibration
│        │     ├──mic_calibration_20190408.yml
│        │     └── ...
│        └── 20200818
│        │     ├──rpi7_10cm_before.csv
│        │     ├──ethoconfig_rpi7_10cm_before.yml
│        │     ├──rpi7_10cm_after.csv
│        │     └──ethoconfig_rpi7_10cm_after.yml
│        ├── test_calibration.ipynb
│        ├── playback_calibration.ipynb
│        └── calib.py
```


