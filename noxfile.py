"""Nox automation for testing, integration, and running the proxy."""

import nox

# Use the current Python instead of requiring a specific version
nox.options.default_venv_backend = "none"


@nox.session(venv_backend="none")
def test(session):
    """Run unit tests with pytest."""
    session.run("uv", "run", "pytest", "tests/", "-v", "--tb=short", external=True)


@nox.session(venv_backend="none")
def integration(session):
    """Run integration tests (requires LiteLLM with provider installed)."""
    session.run(
        "uv",
        "run",
        "pytest",
        "tests/test_integration.py",
        "-v",
        "--tb=short",
        "-m",
        "integration",
        external=True,
    )


@nox.session(venv_backend="none")
def proxy(session):
    """Start LiteLLM proxy with Agno provider on port 8890."""
    session.run(
        "uv",
        "run",
        "litellm",
        "--config",
        "src/agentllm/proxy_config.yaml",
        "--port",
        "8890",
        "--detailed_debug",
        external=True,
    )


@nox.session(venv_backend="none")
def lint(session):
    """Run linting with ruff."""
    session.run("uv", "run", "ruff", "check", "src/", "tests/", external=True)


@nox.session(venv_backend="none")
def format(session):
    """Format code with ruff."""
    session.run("uv", "run", "ruff", "format", "src/", "tests/", external=True)


@nox.session(venv_backend="none")
def hello(session):
    """Make a hello world request to the proxy (proxy must be running)."""
    import json
    import subprocess
    import time

    print("\n🚀 Testing AgentLLM Proxy...\n")

    # Check if proxy is running
    print("1️⃣  Checking if proxy is running on port 8890...")
    result = subprocess.run(["lsof", "-i:8890"], capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ Proxy is not running!")
        print("\n💡 Start the proxy first:")
        print("   nox -s proxy")
        print("\nOr run in background:")
        print("   nox -s proxy &")
        return

    print("✅ Proxy is running!\n")

    # Test 1: Health check
    print("2️⃣  Testing /health endpoint...")
    result = subprocess.run(
        ["curl", "-s", "http://localhost:8890/health"], capture_output=True, text=True
    )
    print(f"   Response: {result.stdout}\n")

    # Test 2: List models
    print("3️⃣  Testing /v1/models endpoint...")
    result = subprocess.run(
        [
            "curl",
            "-s",
            "http://localhost:8890/v1/models",
            "-H",
            "Authorization: Bearer sk-agno-test-key-12345",
        ],
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(result.stdout)
        models = [m.get("id") for m in data.get("data", [])]
        print(f"   Available models: {models}\n")
    except:
        print(f"   Response: {result.stdout}\n")

    # Test 3: Hello world chat completion
    print("4️⃣  Testing chat completion with agno/release-manager...")
    print("   (Note: This will fail without LLM API keys configured)\n")

    result = subprocess.run(
        [
            "curl",
            "-s",
            "http://localhost:8890/v1/chat/completions",
            "-H",
            "Authorization: Bearer sk-agno-test-key-12345",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(
                {
                    "model": "agno/release-manager",
                    "messages": [{"role": "user", "content": "Hello from nox!"}],
                }
            ),
        ],
        capture_output=True,
        text=True,
    )

    print("   Request:")
    print(
        '   {"model": "agno/release-manager", "messages": [{"role": "user", "content": "Hello from nox!"}]}'
    )
    print("\n   Response:")
    try:
        data = json.loads(result.stdout)
        if "error" in data:
            print(f"   ❌ Error: {data['error']}")
            print(
                "\n   💡 This is expected if agents don't have LLM API keys configured."
            )
            print("      To fix: Add API keys to .env and configure agents with models")
        elif "choices" in data:
            content = data["choices"][0]["message"]["content"]
            print(f"   ✅ Success! Agent responded: {content}")
        else:
            print(f"   {json.dumps(data, indent=2)}")
    except:
        print(f"   {result.stdout}")

    print("\n✨ Test complete!\n")
