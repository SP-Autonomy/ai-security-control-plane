"""
Demo workflow - Complete end-to-end demonstration
"""

import requests
import time

API_URL = "http://localhost:8000"
GATEWAY_URL = "http://localhost:8001"


def demo():
    print("🚀 AI Security Control Plane - Demo Workflow\n")
    
    # 1. Register an agent
    print("1. Registering agent...")
    agent_data = {
        "name": "demo-agent",
        "nhi_id": "spiffe://demo.com/agent/001",
        "description": "Demo agent for testing",
        "environment": "development",
        "owner": "demo-team",
        "allowed_tools": ["search", "calculate", "summarize"],
        "budget_per_day": 100
    }
    
    response = requests.post(f"{API_URL}/api/agents", json=agent_data)
    if response.status_code == 200:
        agent = response.json()
        print(f"   ✓ Agent registered: ID {agent['id']}\n")
    else:
        print(f"   ✗ Failed to register agent\n")
        return
    
    # 2. Send LLM request through gateway
    print("2. Sending LLM request...")
    llm_request = {
        "prompt": "Summarize this document. My SSN is 123-45-6789 and email is user@example.com",
        "model": "gpt-4",
        "actor": "demo@example.com",
        "agent_id": agent["id"]
    }
    
    response = requests.post(f"{GATEWAY_URL}/ingress", json=llm_request)
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ Request processed")
        print(f"   - Trace ID: {result['trace_id']}")
        print(f"   - Redactions: {result['redactions_applied']}")
        print(f"   - Latency: {result['latency_ms']}ms\n")
    else:
        print("   ✗ Request failed\n")
    
    # 3. Check posture score
    print("3. Computing posture score...")
    time.sleep(1)
    response = requests.get(f"{API_URL}/api/posture/{agent['id']}")
    if response.status_code == 200:
        posture = response.json()
        print(f"   ✓ Overall Score: {posture['overall_score']}/100")
        print(f"   - Registry: {posture['registry_score']}")
        print(f"   - Tools: {posture['tools_score']}")
        print(f"   - Tracing: {posture['tracing_score']}")
        print(f"   - DLP: {posture['dlp_score']}")
        print(f"   - Policy: {posture['policy_score']}\n")
    else:
        print("   ✗ Failed to compute posture\n")
    
    # 4. List policies
    print("4. Listing policies...")
    response = requests.get(f"{API_URL}/api/policies/")
    if response.status_code == 200:
        policies = response.json()
        print(f"   ✓ Found {len(policies)} policies:")
        for policy in policies:
            status = "enabled" if policy["enabled"] else "disabled"
            print(f"   - {policy['name']} v{policy['version']} ({status})")
        print()
    else:
        print("   ✗ Failed to list policies\n")
    
    print("✅ Demo complete!")
    print(f"\n📊 View dashboard: http://localhost:8501")
    print(f"📖 API docs: http://localhost:8000/docs")


if __name__ == "__main__":
    demo()
