"""
Load default policy bundles into the database
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from control_plane.api.models import Policy
from control_plane.api.init_db import SessionLocal

# Default policies aligned with NIST AI RMF and OWASP
DEFAULT_POLICIES = [
    {
        "name": "DLP Guard",
        "version": "1.0.0",
        "category": "data_protection",
        "description": "Prevents PII leakage by enforcing redaction policies",
        "enabled": True,
        "dry_run": False,
        "tags": ["dlp", "pii", "nist-govern"],
        "rego_code": """
package dlp_guard

# Allow request if no PII detected
default allow = true

# Deny if PII found and not redacted
deny[msg] {
    input.pii_categories
    count(input.pii_categories) > 0
    count(input.redactions_applied) == 0
    msg := sprintf("PII detected but not redacted: %v", [input.pii_categories])
}

# Allow if PII was properly redacted
allow {
    count(input.pii_categories) == count(input.redactions_applied)
}
"""
    },
    {
        "name": "Tool Allowlist",
        "version": "1.0.0",
        "category": "access_control",
        "description": "Enforces tool usage restrictions per agent",
        "enabled": True,
        "dry_run": False,
        "tags": ["tools", "access-control", "owasp"],
        "rego_code": """
package tool_allowlist

# Default deny for tool usage
default allow = false

# Allow if tool is in agent's allowed_tools list
allow {
    input.tool_name
    input.agent.allowed_tools[_] == input.tool_name
}

# Deny with reason if tool not allowed
deny[msg] {
    input.tool_name
    not allow
    msg := sprintf("Tool '%s' not in allowlist for agent '%s'", [input.tool_name, input.agent.name])
}
"""
    },
    {
        "name": "RAG Context Policy",
        "version": "1.0.0",
        "category": "rag_security",
        "description": "Validates RAG document sources and prevents injection",
        "enabled": True,
        "dry_run": False,
        "tags": ["rag", "injection", "mitre-atlas"],
        "rego_code": """
package rag_context

# Default allow for RAG queries
default allow = true

# Check for injection patterns in RAG documents
deny[msg] {
    doc := input.rag_chunks[_]
    contains(lower(doc.content), "ignore previous instructions")
    msg := sprintf("Injection attempt detected in RAG document: %s", [doc.id])
}

deny[msg] {
    doc := input.rag_chunks[_]
    contains(lower(doc.content), "system prompt")
    msg := sprintf("Prompt leakage attempt in RAG document: %s", [doc.id])
}

# Allow if all documents pass validation
allow {
    count(deny) == 0
}
"""
    }
]


def load_policies(db: Session):
    """Load default policies into database"""
    print("Loading default policies...")
    
    loaded_count = 0
    skipped_count = 0
    
    for policy_data in DEFAULT_POLICIES:
        # Check if policy already exists
        existing = db.query(Policy).filter(
            Policy.name == policy_data["name"],
            Policy.version == policy_data["version"]
        ).first()
        
        if existing:
            print(f"  ⊘ Skipping '{policy_data['name']}' v{policy_data['version']} (already exists)")
            skipped_count += 1
            continue
        
        # Create new policy
        policy = Policy(**policy_data)
        db.add(policy)
        db.commit()
        
        print(f"  ✓ Loaded '{policy_data['name']}' v{policy_data['version']}")
        loaded_count += 1
    
    print(f"\n✓ Loaded {loaded_count} policies ({skipped_count} skipped)")
    return loaded_count


if __name__ == "__main__":
    db = SessionLocal()
    try:
        count = load_policies(db)
        
        # Verify
        all_policies = db.query(Policy).all()
        print(f"\nTotal policies in database: {len(all_policies)}")
        
        for p in all_policies:
            status = "✓ enabled" if p.enabled else "✗ disabled"
            print(f"  - {p.name} v{p.version} ({status})")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()