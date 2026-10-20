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


def add_chat_id(d: dict, path: str = "root") -> None:
    """
    Open WebUI (0.9.x) fails with "'NoneType' object has no attribute 'startswith'"
    when a request has no chat_id. An empty chat_id is treated as a temporary chat.
    """
    extra_body = d.get("extra_body") or {}
    if "chat_id" not in extra_body:
        extra_body["chat_id"] = ""
        d["extra_body"] = extra_body
        print(f"[AddChatId] Added empty chat_id to {path}.extra_body")


# Upstream errors that are hard to read in opencode / Claude Code, and what to do about them
ERROR_HINTS = [
    (
        lambda status, text: status in (401, 403) or "401 Unauthorized" in text,
        "MSK rejected the session token (expired or invalid). Put a fresh token in "
        ".auth.env; the proxy restarts automatically on the next aiportal-opencode / aiportal-claude launch.",
    ),
    (
        lambda status, text: "Model not found" in text,
        "The MSK endpoint no longer offers this model. "
        "Run ./aiportal.py sync --apply to update the model list.",
    ),
    (
        lambda status, text: "'startswith'" in text,
        "The MSK endpoint rejected the request format; check add_chat_id in custom_callbacks.py.",
    ),
]


def add_error_hint(exc: Exception) -> None:
    """Prefix a plain-language hint to the exception message (shown to the client)."""
    text = str(exc)
    if text.startswith("[MSK proxy]"):
        return
    status = getattr(exc, "status_code", None)
    for matches, hint in ERROR_HINTS:
        if matches(status, text):
            if hasattr(exc, "message"):
                exc.message = f"[MSK proxy] {hint} Original error: {exc.message}"
            return


def modify_params_hook(data: dict, *args, **kwargs) -> dict:
    """
    Hook function to modify request params before sending.
    This is called by litellm.modify_params.
    """
    print(f"[modify_params_hook] Processing request...")
    strip_params_from_dict(data, "data")
    add_chat_id(data, "data")
    return data


class StripUnsupportedParams(CustomLogger):
    """
    Callback to strip parameters that Bedrock/MSK WebUI doesn't support.
    """

    def log_pre_api_call(self, model, messages, kwargs):
        """Called before the API call - modify kwargs to strip unsupported params."""
        print(f"[StripUnsupportedParams] log_pre_api_call for model: {model}")
        strip_params_from_dict(kwargs, "kwargs")
        add_chat_id(kwargs, "kwargs")

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
        add_chat_id(data, "data")
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
    add_chat_id(kwargs, "kwargs")
    try:
        return original_completion(*args, **kwargs)
    except Exception as e:
        add_error_hint(e)
        raise


async def patched_acompletion(*args, **kwargs):
    """Patched async completion function that strips params before calling original."""
    print(f"[patched_acompletion] Stripping params from kwargs")
    strip_params_from_dict(kwargs, "kwargs")
    add_chat_id(kwargs, "kwargs")
    try:
        return await original_acompletion(*args, **kwargs)
    except Exception as e:
        add_error_hint(e)
        raise


def patch_litellm():
    """Apply patches to litellm to strip unsupported params."""
    litellm.completion = patched_completion
    litellm.acompletion = patched_acompletion
    print("[patch_litellm] Patched litellm.completion and litellm.acompletion")


# Auto-patch on import
patch_litellm()
