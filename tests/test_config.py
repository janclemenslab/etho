from etho.utils.config import readconfig

print('test')
def test_yaml_types():
    cfg = readconfig('tests/test_config.yaml')
    assert isinstance(cfg['integer'], int)
    assert isinstance(cfg['float'], float)
    assert isinstance(cfg['list'], list)
