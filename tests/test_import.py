"""Import Test."""

import importlib
import pkgutil

import shotgrid_casbin_adapter


def test_imports():
    """Test import modules."""
    prefix = "{}.".format(shotgrid_casbin_adapter.__name__)  # noqa
    iter_packages = pkgutil.walk_packages(
        shotgrid_casbin_adapter.__path__,
        prefix,
    )
    for _, name, _ in iter_packages:
        module_name = name if name.startswith(prefix) else prefix + name
        importlib.import_module(module_name)
