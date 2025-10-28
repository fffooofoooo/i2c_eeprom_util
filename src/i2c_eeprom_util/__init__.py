from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("i2c_eeprom_util")
except PackageNotFoundError:
    __version__ = "0.0.0"
