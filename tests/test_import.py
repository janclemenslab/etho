import importlib
import pkgutil
import types


def import_all_modules(package: types.ModuleType) -> None:
    """Recursively import all modules in a package.

    This function walks through all submodules of a given package and attempts
    to import each one. It is intended as a smoke test to catch import-time
    errors such as missing dependencies, syntax errors, or circular imports.

    Args:
        package (types.ModuleType): Imported top-level package object
            (e.g. ``import mypkg; import_all_modules(mypkg)``).

    Raises:
        ImportError: If any submodule fails to import.
    """
    package_path = [str(path) for path in package.__path__]
    prefix = package.__name__ + "."

    for module_info in pkgutil.walk_packages([str(package_path)], prefix):
        importlib.import_module(module_info.name)


def test_import_all():
    import etho

    import_all_modules(etho)
