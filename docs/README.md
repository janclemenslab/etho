
# Eth-O-Matic

## installation

### HEAD
dependencies:
python 3.5, flask, ...
- for zerorpc to work, need to install git version (https://github.com/msgpack/msgpack-python/commit/3a098851bea500ef1ffde856a60d80ddab230dee) and `python setup.py install` (uninstall old version first)
- `pip install wxpython`

### CLIENT
- deploy: https://github.com/billw2/rpi-clone
- download and install [berryconda3](https://github.com/jjhelmus/berryconda) (will install py3.6) to `~/miniconda3`
- add rpi channel to conda: `conda config --add channels rpi`
- install packages:
    conda install h5py numpy cython pandas
    conda install pyzmq ipython pillow
    pip install zerorpc pygame 'picamera[array]' 
    [required? msgpack-numpy fabric3]
- [not required but how knows]: build/install opencv
- LED control and temp/humidity reads via arduino connected to rpi by USB, 
    + [arduino micro](https://store.arduino.cc/arduino-micro) has all the I/O needed and is powered via USB
    + [connect rpi and arduino](https://oscarliang.com/connect-raspberry-pi-and-arduino-usb-cable/), requires [pyserial](https://pypi.python.org/pypi/pyserial) for communication
    + [control arduino from rpi](https://github.com/nanpy/nanpy)
    + [controlling LEDs via PWM](https://www.arduino.cc/en/Tutorial/SecretsOfArduinoPWM), [library](https://github.com/micooke/PWM), also [this](http://r6500.blogspot.de/2014/12/fast-pwm-on-arduino-leonardo.html) and [this](http://r6500.blogspot.de/2014/12/fast-pwm-on-arduino-leonardo.html)
    + [temp/humidity sensor](https://github.com/jasiek/HTU21D) or [this](https://github.com/dalexgray/RaspberryPI_HTU21DF) or [DHT22](https://github.com/adafruit/Adafruit_Python_DHT)
    + [sync led](http://www.instructables.com/id/Creating-An-Audio-Reactive-LED-Circuit/), may also be useful for switching [background light](https://www.raspberrypi.org/forums/viewtopic.php?t=197339)



## Inspirations
remote control rpi via flask webserver:
http://mattrichardson.com/Raspberry-Pi-Flask/
https://forum.poppy-project.org/t/flask-quick-web-interface-for-robots/2217/5

https://learn.adafruit.com/raspipe-a-raspberry-pi-pipeline-viewer-part-2/miniature-web-applications-in-python-with-flask

http://randomnerdtutorials.com/raspberry-pi-web-server-using-flask-to-control-gpios/

for remote control [pizco](https://pizco.readthedocs.io/en/latest/)

data formats: http://neo.readthedocs.io/en/0.5.0/core.html

### ethoscope:
[code](https://github.com/gilestrolab/ethoscope)
[paper](http://www.biorxiv.org/content/early/2017/04/02/113647)

### flypi
[code](https://github.com/amchagas/Flypi)
[paper](http://www.biorxiv.org/content/early/2017/03/31/122812)
[setup](https://hackaday.io/project/5059-flypi-cheap-microscopeexperimental-setup
)
### flask
[flask](http://flask.pocoo.org)
[sql-extension](http://flask-sqlalchemy.pocoo.org/2.1/)

## wx

### data formats
[hdf5](http://neo.readthedocs.io/en/0.5.0/core.html)
[why hdf5 is slow](http://cyrille.rossant.net/moving-away-hdf5/)
[flymovieformat](https://github.com/motmot/flymovieformat)

# temperature/humidity control/recording
https://www.phidgets.com

# ethoscope parts
- Bauanleitung: https://qgeissmann.gitbooks.io/ethoscope-manual/building-and-installation/ethoscope.html
- 3D Modelle aller Bauteile: https://cad.onshape.com/documents/56ac957ce4b06a92e0ed7352/w/0af5bcd5aa6f698123921d81/e/9491b49b9158a49e2b29f937
- 3D Modelle der Kammern, die die Fliegen halten und unten in die Apparatur eingeschoben werden (die werde ich wahrscheinlich für meine Versuch anpassen): https://cad.onshape.com/documents/56ac92e6e4b07682577ddeb3/w/f75f54bb0e265153acfec7dd/e/274eb5822aae8e8a5af445db

# build opencv on rpi3
``` shell
PREFIX="/home/pi/miniconda3"
PYTHON="/home/pi/miniconda3/bin/python3.6"
DYNAMIC_EXT="so"
PY_VER_M="3.6m"

OCV1="-DBUILD_opencv_python3=TRUE -DPYTHON3_EXECUTABLE=$PYTHON -DPYTHON3_LIBRARY=${PREFIX}/lib/libpython${PY_VER_M}.${DYNAMIC_EXT}"
OCV2="-DPYTHON3_NUMPY_INCLUDE_DIRS=$PREFIX/lib/python3.6/site-packages/numpy/core/include/ -DPYTHON3_PACKAGES_PATH=$PREFIX/lib/python3.6/site-packages"
OCV3="-DPYTHON3_INCLUDE_DIR=$PREFIX/include/python3.6m/ -DPYTHON2_EXECUTABLE=doo"
cmake .. $OCV1 $OCV2 $OCV3 -DWITH_CUDA=0 -DWITH_FFMPEG=1 -DBUILD_opencv_python2=FALSE -DPYTHON3_LIBRARY=/home/pi/miniconda3/lib/libpython3.6m.so
# cp /home/pi/miniconda3/include/python3.6m/*.h .
# cp /home/pi/miniconda3/include/*.h .
make -j4
sudo make install
```