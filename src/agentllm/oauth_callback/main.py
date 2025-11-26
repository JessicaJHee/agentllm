"""OAuth callback server for AgentLLM authentication.

This FastAPI server handles OAuth callbacks from multiple providers
(Google Drive, GitHub, etc.) and stores tokens in the shared TokenStorage database.

The server runs as a sidecar container in the same pod as the LiteLLM proxy,
sharing the SQLite database at /app/tmp/agent-data/agno_sessions.db.
"""

import os
from datetime import UTC, datetime

from agno.db.sqlite import SqliteDb
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from agentllm.db.encryption import EncryptionKeyMissingError
from agentllm.db.token_storage import TokenStorage
from agentllm.oauth_callback.providers import ProviderRegistry

# Initialize FastAPI app
app = FastAPI(
    title="AgentLLM OAuth Callback Server",
    description="Generic OAuth callback server for AgentLLM supporting multiple providers",
    version="1.0.0",
)

# Get shared database path (same as custom_handler)
AGENTLLM_DATA_DIR = os.getenv("AGENTLLM_DATA_DIR", "/app/tmp")
DB_PATH = os.path.join(AGENTLLM_DATA_DIR, "agno_sessions.db")

# Discover and register all toolkit token types
from agentllm.agents.toolkit_configs import discover_and_register_toolkits  # noqa: E402

discover_and_register_toolkits()

# Initialize shared database and token storage (with encryption)
shared_db = SqliteDb(db_file=DB_PATH)
try:
    token_storage = TokenStorage(agno_db=shared_db)  # Loads key from AGENTLLM_TOKEN_ENCRYPTION_KEY env var
    logger.info("OAuth callback server: token storage initialized with encryption enabled")
except EncryptionKeyMissingError as e:
    logger.error(f"CRITICAL: Failed to initialize token storage: {e}")
    logger.error("Ensure AGENTLLM_TOKEN_ENCRYPTION_KEY is set correctly")
    raise  # Fail fast

# Initialize provider registry
provider_registry = ProviderRegistry(token_storage=token_storage)

logger.info(f"OAuth callback server initialized with database at {DB_PATH}")
logger.info(f"Configured providers: {', '.join(provider_registry.get_configured_providers())}")


@app.get("/")
async def root():
    """Root endpoint with server status and available providers."""
    configured_providers = provider_registry.get_configured_providers()
    all_providers = list(provider_registry.get_all_providers().keys())

    return {
        "service": "AgentLLM OAuth Callback Server",
        "status": "running",
        "database": DB_PATH,
        "providers": {
            "all": all_providers,
            "configured": configured_providers,
        },
        "endpoints": {
            "health": "/health",
            "oauth_callback": "/agentllm/oauth/callback/{provider}",
        },
        "example_urls": {provider: f"/agentllm/oauth/callback/{provider}" for provider in all_providers},
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {
        "status": "healthy",
        "database": "connected" if token_storage else "unavailable",
        "configured_providers": provider_registry.get_configured_providers(),
    }


@app.get("/agentllm/oauth/callback/{provider}", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    provider: str,
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="State parameter (signed JWT token)"),
):
    """Generic OAuth callback endpoint for all providers.

    Args:
        request: FastAPI request object
        provider: Provider name (google, github, etc.)
        code: OAuth authorization code
        state: Signed JWT state token containing user_id (for CSRF protection)

    Returns:
        HTML response with success or error message
    """
    # Validate state token early for logging and display purposes
    # Provider will validate it again for security
    from agentllm.oauth_callback.state_validation import StateTokenError, validate_state_token

    try:
        user_id = validate_state_token(state)
        logger.info(f"🔔 OAuth callback received for provider={provider}, user_id={user_id}")
        logger.debug(f"Full callback URL: {request.url}")
    except StateTokenError as e:
        logger.error(f"Invalid state token in OAuth callback: {e}")
        return HTMLResponse(
            content="""
            <html>
                <head><title>OAuth Error</title></head>
                <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
                    <h1 style="color: #dc3545;">❌ Authorization Failed</h1>
                    <p style="font-size: 18px; margin-top: 20px;">
                        Invalid or expired authorization request.
                    </p>
                    <p style="color: #6c757d; margin-top: 20px;">
                        Please restart the authorization process.
                    </p>
                </body>
            </html>
            """,
            status_code=400,
        )

    # Get provider from registry
    oauth_provider = provider_registry.get_provider(provider)

    if not oauth_provider:
        logger.error(f"Unknown OAuth provider: {provider}")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>OAuth Error</title></head>
                <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
                    <h1 style="color: #dc3545;">❌ Unknown Provider</h1>
                    <p style="font-size: 18px; margin-top: 20px;">
                        OAuth provider '{provider}' is not supported.
                    </p>
                    <p style="color: #6c757d; margin-top: 20px;">
                        Supported providers: {", ".join(provider_registry.get_all_providers().keys())}
                    </p>
                </body>
            </html>
            """,
            status_code=400,
        )

    # Check if provider is configured
    if not oauth_provider.is_configured():
        logger.error(f"OAuth provider {provider} is not configured")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>OAuth Error</title></head>
                <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
                    <h1 style="color: #dc3545;">❌ Configuration Error</h1>
                    <p style="font-size: 18px; margin-top: 20px;">
                        OAuth credentials for '{provider}' are not configured on the server.
                    </p>
                    <p style="color: #6c757d; margin-top: 20px;">
                        Please contact your administrator.
                    </p>
                </body>
            </html>
            """,
            status_code=500,
        )

    # Reconstruct redirect URI
    # In production: https://oauth.apps.ext.spoke.prod.us-east-1.aws.paas.redhat.com/agentllm/oauth/callback/{provider}
    # In local dev: http://localhost:8501/agentllm/oauth/callback/{provider}
    callback_base_url = os.getenv("AGENTLLM_OAUTH_CALLBACK_BASE_URL", str(request.base_url).rstrip("/"))
    redirect_uri = f"{callback_base_url}/agentllm/oauth/callback/{provider}"

    logger.debug(f"Using redirect URI: {redirect_uri}")

    # Exchange code for token
    success, message = oauth_provider.exchange_code_for_token(
        code=code,
        state=state,
        redirect_uri=redirect_uri,
    )

    if success:
        # Return success HTML page
        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>Authentication Successful</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                </head>
                <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center; max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #28a745;">✅ Authentication Successful!</h1>
                    <p style="font-size: 18px; margin-top: 20px;">
                        Your {provider.title()} account has been linked successfully.
                    </p>
                    <p style="color: #6c757d; margin-top: 20px;">
                        You can now return to the chat and start using {provider.title()} features.
                    </p>
                    <p style="color: #6c757d; font-size: 14px; margin-top: 40px;">
                        User ID: <code>{user_id}</code><br>
                        Provider: <code>{provider}</code><br>
                        Authenticated at: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")}
                    </p>
                    <hr style="margin: 40px auto; width: 200px; border: 1px solid #dee2e6;">
                    <p style="color: #6c757d; font-size: 12px;">
                        You can safely close this window.
                    </p>
                </body>
            </html>
            """
        )
    else:
        # Return error HTML page
        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>Authentication Failed</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                </head>
                <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center; max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #dc3545;">❌ Authentication Failed</h1>
                    <p style="font-size: 18px; margin-top: 20px;">
                        Unable to complete authentication with {provider.title()}.
                    </p>
                    <p style="color: #6c757d; margin-top: 20px;">
                        Error: {message}
                    </p>
                    <p style="color: #6c757d; margin-top: 20px;">
                        Please try again or contact support if the problem persists.
                    </p>
                    <hr style="margin: 40px auto; width: 200px; border: 1px solid #dee2e6;">
                    <p style="color: #6c757d; font-size: 12px;">
                        You can close this window and try again.
                    </p>
                </body>
            </html>
            """,
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn

    # Get port from environment or default to 8501
    port = int(os.getenv("OAUTH_CALLBACK_PORT", "8501"))

    logger.info(f"Starting OAuth callback server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
