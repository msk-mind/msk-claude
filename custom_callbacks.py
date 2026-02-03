"""
Custom LiteLLM modifications to strip unsupported parameters before sending to backend.
"""

import litellm
from litellm.integrations.custom_logger import CustomLogger
from typing import Any, Dict, Optional


# Parameters to strip from all requests
PARAMS_TO_STRIP = [
    "output_config",
    "thinking",
    "thinking_budget",
    "budget_tokens",
]


def strip_params_from_dict(d: dict, path: str = "root") -> None:
    """Recursively strip unsupported parameters from a dictionary."""
    if not isinstance(d, dict):
        return

    for param in PARAMS_TO_STRIP:
        if param in d:
            print(f"[StripParams] Removing '{param}' from {path}")
            del d[param]

    # Recursively check nested dicts
    for key, value in list(d.items()):
        if isinstance(value, dict):
            strip_params_from_dict(value, f"{path}.{key}")


def modify_params_hook(data: dict, *args, **kwargs) -> dict:
    """
    Hook function to modify request params before sending.
    This is called by litellm.modify_params.
    """
    print(f"[modify_params_hook] Processing request...")
    strip_params_from_dict(data, "data")
    return data


class StripUnsupportedParams(CustomLogger):
    """
    Callback to strip parameters that Bedrock/MSK WebUI doesn't support.
    """

    def log_pre_api_call(self, model, messages, kwargs):
        """Called before the API call - modify kwargs to strip unsupported params."""
        print(f"[StripUnsupportedParams] log_pre_api_call for model: {model}")
        strip_params_from_dict(kwargs, "kwargs")

    async def async_pre_call_hook(
        self,
        user_api_key_dict,
        cache,
        data: dict,
        call_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Async hook called before the LLM API call.
        Returns modified data dict or raises exception to reject.
        """
        print(f"[StripUnsupportedParams] async_pre_call_hook, call_type: {call_type}")
        strip_params_from_dict(data, "data")
        return data


# Create instance for LiteLLM to use
strip_params_callback = StripUnsupportedParams()


# Patch both sync and async completion functions
original_completion = litellm.completion
original_acompletion = litellm.acompletion


def patched_completion(*args, **kwargs):
    """Patched completion function that strips params before calling original."""
    print(f"[patched_completion] Stripping params from kwargs")
    strip_params_from_dict(kwargs, "kwargs")
    return original_completion(*args, **kwargs)


async def patched_acompletion(*args, **kwargs):
    """Patched async completion function that strips params before calling original."""
    print(f"[patched_acompletion] Stripping params from kwargs")
    strip_params_from_dict(kwargs, "kwargs")
    return await original_acompletion(*args, **kwargs)


def patch_litellm():
    """Apply patches to litellm to strip unsupported params."""
    litellm.completion = patched_completion
    litellm.acompletion = patched_acompletion
    print("[patch_litellm] Patched litellm.completion and litellm.acompletion")


# Auto-patch on import
patch_litellm()
