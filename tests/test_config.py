from utils.config import readconfig

# def test_global_config():
#     assert len(config)>0, 'could not read global config file `~/.ethoconfig.ini`'

def test_yaml_types():
    cfg = readconfig('tests/test_config.yaml')
    assert isinstance(cfg['integer'], int)
    assert isinstance(cfg['float'], float)
    assert isinstance(cfg['list'], list)
