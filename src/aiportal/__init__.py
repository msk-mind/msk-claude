"""Use opencode and Claude Code with the models on MSK's AI Portal, through a local LiteLLM proxy."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aiportal")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0+unknown"
