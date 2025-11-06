"""Test script to verify agent caching is working correctly."""

import requests
import json

BASE_URL = "http://localhost:8890"
API_KEY = "sk-agno-test-key-12345"

def make_request(model: str, message: str, user_id: str, temperature: float = None):
    """Make a chat completion request to the proxy."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-OpenWebUI-User-Id": user_id,
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
    }

    if temperature is not None:
        payload["temperature"] = temperature

    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload
    )

    return response.json()

def test_agent_caching():
    """Test that agents are cached properly."""
    print("=== Testing Agent Caching ===\n")

    # Test 1: Same user, same agent, same params - should use cached agent
    print("Test 1: Making 3 requests with same user_id, same agent, same params...")
    print("Expected: First request creates agent, next 2 reuse cached agent\n")

    for i in range(3):
        print(f"Request {i+1}...")
        result = make_request(
            model="agno/echo",
            message=f"Test message {i+1}",
            user_id="user_001"
        )
        print(f"Response: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:100]}...\n")

    # Test 2: Different user, same agent - should create new cached agent
    print("\nTest 2: Making request with different user_id...")
    print("Expected: New agent created for user_002\n")

    result = make_request(
        model="agno/echo",
        message="Different user message",
        user_id="user_002"
    )
    print(f"Response: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:100]}...\n")

    # Test 3: Same user, same agent, different temperature - should create new cached agent
    print("\nTest 3: Making request with same user but different temperature...")
    print("Expected: New agent created with different temperature\n")

    result = make_request(
        model="agno/echo",
        message="Message with different temp",
        user_id="user_001",
        temperature=0.9
    )
    print(f"Response: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:100]}...\n")

    # Test 4: Different agent type - should create new cached agent
    print("\nTest 4: Making request with different agent type...")
    print("Expected: New agent created for 'assistant' type\n")

    result = make_request(
        model="agno/assistant",
        message="Hello assistant",
        user_id="user_001"
    )
    print(f"Response: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:100]}...\n")

    print("\n=== Check agno_handler.log for caching messages ===")
    print("Look for lines like:")
    print("  - 'Creating new agent for key: ...'")
    print("  - 'Using cached agent for key: ...'")
    print("  - 'Cached agent. Total cached agents: N'")

if __name__ == "__main__":
    test_agent_caching()
