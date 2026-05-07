from pathlib import Path

import pytest

from etho.utils import config


TEST_CONFIG_FILE = Path(__file__).with_name("test_config.yaml")


def test_yaml_types():
    cfg = config.readconfig(str(TEST_CONFIG_FILE))
    assert isinstance(cfg['integer'], int)
    assert isinstance(cfg['float'], float)
    assert isinstance(cfg['list'], list)


def test_missing_default_config_raises(monkeypatch, tmp_path):
    missing_config = tmp_path / "ethoconfig" / "ethoconfig.yml"
    monkeypatch.setattr(config, "GLOBALCONFIGFILEPATH", str(missing_config))

    with pytest.raises(FileNotFoundError, match="No config file found"):
        config.readconfig()
