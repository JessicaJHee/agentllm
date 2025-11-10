"""Stub handler for LiteLLM custom provider path resolution.

LiteLLM loads custom handlers using file-based resolution relative to the config
file location, not Python module imports. Since our config is at the project root
(proxy_config.yaml), LiteLLM looks for handlers relative to that location.

This stub file allows LiteLLM to find the handler while keeping the actual
implementation organized in src/agentllm/custom_handler.py.

See CLAUDE.md for more details on this pattern.
"""

from agentllm.custom_handler import agno_handler

__all__ = ["agno_handler"]
