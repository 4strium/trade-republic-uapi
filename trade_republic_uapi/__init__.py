from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("trade-republic-uapi")
except PackageNotFoundError:
    __version__ = "unknown"
