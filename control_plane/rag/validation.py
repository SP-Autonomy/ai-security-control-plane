"""
Security validation for RAG documents
Adapted from Lab 02 with production-grade patterns
"""

import re
import os
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


# Allowed sources (allowlist)
ALLOWED_SOURCES = {
    "internal_docs",
    "public_website",
    "verified_partners",
    "knowledge_base",
    "company_wiki",
    "redteam"  # For testing only
}

# Suspicious patterns from Lab 02 (proven in production)
SUSPICIOUS_PATTERNS = [
    r"ignore previous instructions",
    r"disregard all",
    r"reveal.*system prompt",
    r"exfiltrate",
    r"ignore all previous",
    r"disregard.*safety",
    r"disregard.*security",
    r"ignore all context",
    r"bypass.*policy",
    r"override.*rules",
]

# Additional injection patterns
INJECTION_PATTERNS = [
    r"<script>",
    r"javascript:",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"INSERT\s+INTO",
    r"<\s*img\s+src",
    r"onerror\s*=",
    r"onclick\s*=",
]

# Test mode flag
TEST_MODE = os.getenv("RAG_TEST_MODE", "false").lower() == "true"


def validate_source(source: str) -> Tuple[bool, str]:
    """
    Validate if source is in allowlist
    
    Returns:
        (is_valid, message)
    """
    if source in ALLOWED_SOURCES:
        return True, f"Source '{source}' is allowed"
    else:
        logger.warning(f"Source validation failed: {source}")
        return False, f"Source '{source}' not in allowlist. Allowed: {ALLOWED_SOURCES}"


def detect_injection_in_content(content: str) -> Tuple[bool, List[str]]:
    """
    Detect injection patterns in content (for ingestion validation)
    
    Returns:
        (injection_detected, patterns_found)
    """
    patterns_found = []
    content_lower = content.lower()
    
    # Check suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            patterns_found.append(pattern)
            logger.warning(f"Suspicious pattern detected: {pattern}")
    
    # Check injection patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            patterns_found.append(pattern)
            logger.warning(f"Injection pattern detected: {pattern}")
    
    injection_detected = len(patterns_found) > 0
    
    return injection_detected, patterns_found


def validate_document(
    content: str,
    source: str,
    threshold: int = 2
) -> Tuple[bool, str]:
    """
    Validate document before ingestion (Lab 02 logic)
    
    Args:
        content: Document content
        source: Source identifier
        threshold: Number of suspicious patterns to trigger rejection (default: 2)
    
    Returns:
        (is_valid, reason)
    """
    # Count suspicious patterns
    suspicious_count = 0
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            suspicious_count += 1
    
    # Allow red team documents in test mode
    if TEST_MODE and source == "redteam":
        return True, "redteam_document_test_mode"
    
    # Block if threshold exceeded (likely attack)
    if suspicious_count >= threshold:
        logger.warning(
            f"Document rejected: {suspicious_count} suspicious patterns (threshold: {threshold})"
        )
        return False, f"rejected_suspicious_content ({suspicious_count} patterns)"
    
    return True, "accepted"


def check_content_safety(content: str) -> Tuple[bool, str]:
    """
    Check if content is safe to ingest
    
    Returns:
        (is_safe, message)
    """
    # Check length
    if len(content) > 100000:  # 100KB limit
        return False, "Content exceeds size limit (100KB)"
    
    if len(content) < 10:
        return False, "Content too short (minimum 10 characters)"
    
    # Check for binary data
    try:
        content.encode('utf-8')
    except UnicodeEncodeError:
        return False, "Content contains invalid characters"
    
    # Check for injection using Lab 02 logic
    is_valid, reason = validate_document(content, "unknown")
    if not is_valid:
        return False, reason
    
    return True, "Content is safe"


def sanitize_html(text: str) -> str:
    """
    Remove HTML tags from text (Lab 02 sanitization)
    
    Returns:
        Sanitized text
    """
    TAG_RX = re.compile(r"<[^>]+>")
    return TAG_RX.sub("", text)


def check_retrieved_context(context: str) -> Tuple[bool, List[str]]:
    """
    Check retrieved context for injection patterns before LLM call
    This is CRITICAL - validates content at retrieval time, not just ingestion
    
    Returns:
        (is_safe, patterns_found)
    """
    patterns_found = []
    context_lower = context.lower()
    
    # Check for injection attempts in retrieved content
    for pattern in SUSPICIOUS_PATTERNS + INJECTION_PATTERNS:
        if re.search(pattern, context_lower, re.IGNORECASE):
            patterns_found.append(pattern)
            logger.warning(f"Injection pattern in retrieved context: {pattern}")
    
    is_safe = len(patterns_found) == 0
    
    if not is_safe:
        logger.error(
            f"Retrieved context contains {len(patterns_found)} injection patterns - BLOCKING"
        )
    
    return is_safe, patterns_found


def validate_metadata(metadata: dict) -> Tuple[bool, str]:
    """
    Validate metadata structure
    
    Returns:
        (is_valid, message)
    """
    required_fields = ["source"]
    
    for field in required_fields:
        if field not in metadata:
            return False, f"Missing required field: {field}"
    
    # Validate source
    is_valid, msg = validate_source(metadata["source"])
    if not is_valid:
        return False, msg
    
    return True, "Metadata is valid"


def get_trust_level(source: str) -> str:
    """Get trust level for source"""
    if source == "redteam":
        return "redteam"
    elif source in ["internal_docs", "knowledge_base", "company_wiki"]:
        return "internal"
    else:
        return "external"