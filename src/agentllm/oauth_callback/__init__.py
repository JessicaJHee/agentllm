"""OAuth callback server for AgentLLM.

This package provides a generic OAuth callback server that handles OAuth flows
for multiple providers (Google Drive, GitHub, etc.) eliminating the need for
manual code copy/paste.

The callback server runs as a sidecar container in the same pod as the LiteLLM
proxy, sharing the SQLite database for token storage.
"""
