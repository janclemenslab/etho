# Etho: master & service

## TODO
- [ ] switch over to yaml for config reading (since this will preserve types)
- [ ] switch over to new zerorpc and pickle on localhost tasks
- [ ] present logging information within gui
- [ ] make gui more responsive through async
- [ ] make protocols editable so small changes are more easily done (use traisui)
- [ ] installation instructions (where to copy `.ethoconfig.ini`)
- [ ] refactor? ethoservice->services, ethomaster->master?
- [ ] copy ethoservice wiki

## deploy
pip uninstall ethoservice
pip install -e .

 - on head only:
# cp config/deviceconfig/.ethoconfigRPI.ini -> ~/.ethoconfig.ini

## Services
- CAM - picamera
- SND - audio output
- SLP/SLE - dummy services for testing purposes
- LED (not yet implemented) - GPIO
- THU (not yet implemented) - temperature and humidity sensor

## Documentation
- [service description](https://github.com/janclemenslab/ethoservice/wiki/Services)
- [node setup](https://github.com/janclemenslab/ethoservice/wiki/Node-setup)
