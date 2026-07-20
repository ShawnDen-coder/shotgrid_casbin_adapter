"""ShotGrid Casbin Adapter.

A Casbin policy adapter that enables loading and saving access control
policies from/to Autodesk ShotGrid (formerly Shotgun).
"""

from shotgrid_casbin_adapter.core import Adapter
from shotgrid_casbin_adapter.filter import Filter


__all__: list[str] = ["Adapter", "Filter"]
__author__: str = "shawndeng"
__email__: str = "shawndeng1109@qq.com"
