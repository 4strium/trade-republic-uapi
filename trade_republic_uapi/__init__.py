from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("credit-agricole-uapi")
except PackageNotFoundError:
    __version__ = "unknown"
