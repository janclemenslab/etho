import glob
from importlib import import_module


def test_imports():
    for srv in glob.glob('../ethoservice/*ZeroService.py'):
        srv_name = srv.partition('e/')[-1][:-3]
        try:
            mod_name = f'ethoservice.x{srv_name}'
            import_module(mod_name)
        except Exception as e:
            print(e)
