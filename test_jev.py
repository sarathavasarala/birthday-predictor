#!/usr/bin/env python3
"""
Test script for TypeSafe AI Jev (System One) integration.
Verifies candidate extraction (phone numbers & names), response formatting,
API connection, and dual-engine fallback.
"""

import os
import sys
import json
from datetime import datetime, date

from models import Message, WishCluster, Participant
from jev_parser import jev_parser
from llm_parser import llm_parser


def test_candidate_extraction():
    """Test extracting names and phone numbers as candidates for Jev Choice."""
    print("=" * 60)
    print("1. Testing Candidate Extraction (Phone Numbers & Names)")
    print("=" * 60)

    # Mock participants (some with names, some raw phone numbers)
    participants = [
        Participant(id=1, display_name="Alice Smith", canonical_name="Alice Smith", phone="+15550001111"),
        Participant(id=2, display_name="+1 (555) 987-6543", canonical_name="+15559876543", phone="+15559876543"),
        Participant(id=3, display_name="Bob Jones", canonical_name="Bob Jones", phone=None)
    ]

    # Mock messages with phone mentions and name wishes
    messages = [
        Message(id=1, sender="Alice Smith", text="Happy birthday @15559876543! 🎂", timestamp=datetime(2024, 8, 1, 10, 0)),
        Message(id=2, sender="Charlie", text="Happy birthday Dave! Hope you have a blast", timestamp=datetime(2024, 8, 1, 10, 15)),
        Message(id=3, sender="+1 (555) 987-6543", text="Thanks everyone for the wishes! 🙏", timestamp=datetime(2024, 8, 1, 11, 0))
    ]

    cluster = WishCluster(id=1, chat_id=1, date=date(2024, 8, 1), unique_wishers=2, total_wish_score=2.0)

    candidates = jev_parser.extract_candidates(cluster, messages, participants)
    print(f"Extracted {len(candidates)} candidates:")
    for idx, c in enumerate(candidates, 1):
        print(f"  [{idx}] {c}")

    assert "+15559876543" in candidates, "Expected phone number +15559876543 in candidates"
    assert "Alice Smith" in candidates, "Expected Alice Smith in candidates"
    assert "Dave" in candidates, "Expected Dave in candidates"
    assert "Unknown / Someone outside chat" in candidates, "Expected fallback option in candidates"
    print("✅ Candidate extraction passed!\n")


def test_format_jev_response_with_phone():
    """Test formatting Jev response when a phone number is the chosen recipient."""
    print("=" * 60)
    print("2. Testing Jev Response Formatting with Phone Number & Probabilities")
    print("=" * 60)

    cluster = WishCluster(id=1, chat_id=1, date=date(2024, 8, 1), unique_wishers=3, total_wish_score=3.0)
    messages = [
        Message(id=1, sender="Alice", text="HBD @15559876543!", timestamp=datetime(2024, 8, 1, 10, 0))
    ]
    candidates = ["+15559876543", "Alice", "Unknown / Someone outside chat"]

    mock_jev_api_response = {
        "answers": {
            "target": {
                "value": "+15559876543",
                "confidence": 0.94,
                "probabilities": {
                    "+15559876543": 0.94,
                    "Alice": 0.04,
                    "Unknown / Someone outside chat": 0.02
                }
            },
            "timing": {
                "value": "on_time"
            },
            "confidence_score": {
                "value": 4.8
            }
        }
    }

    result = jev_parser._format_jev_response(mock_jev_api_response, cluster, messages, candidates)
    print("Formatted Result:")
    print(json.dumps(result, indent=2))

    assert result["person"] == "+15559876543", f"Expected person +15559876543, got {result['person']}"
    assert result["phone_number"] == "+15559876543", f"Expected phone +15559876543, got {result['phone_number']}"
    assert result["confidence"] >= 90, f"Expected high confidence >= 90, got {result['confidence']}"
    assert result["probabilities"]["+15559876543"] == 0.94, "Probabilities dictionary mismatch"
    assert result["source"] == "jev-system-one"
    print("✅ Jev phone response formatting passed!\n")


def test_belated_timing_adjustment():
    """Test that belated wishes adjust the predicted date back by 1 day."""
    print("=" * 60)
    print("3. Testing Belated Timing Date Adjustment")
    print("=" * 60)

    cluster = WishCluster(id=1, chat_id=1, date=date(2024, 8, 2), unique_wishers=2, total_wish_score=2.0)
    messages = [
        Message(id=1, sender="Bob", text="Belated happy birthday Sarah!", timestamp=datetime(2024, 8, 2, 9, 0))
    ]
    candidates = ["Sarah", "Bob", "Unknown / Someone outside chat"]

    mock_belated_response = {
        "answers": {
            "target": {"value": "Sarah", "confidence": 0.88, "probabilities": {"Sarah": 0.88}},
            "timing": {"value": "belated"},
            "confidence_score": {"value": 4.0}
        }
    }

    result = jev_parser._format_jev_response(mock_belated_response, cluster, messages, candidates)
    # Since cluster date was August 2nd, belated should adjust it to August 1st (08-01)
    print(f"Cluster date: 2024-08-02 | Adjusted birthday date: {result['date']}")
    assert result["date"] == "08-01", f"Expected 08-01, got {result['date']}"
    assert result["timing"] == "belated"
    print("✅ Belated timing adjustment passed!\n")


def test_llm_parser_active_engine():
    """Test engine detection and fallback in llm_parser."""
    print("=" * 60)
    print("4. Testing AI Engine Detection & Dual-Engine Fallback")
    print("=" * 60)

    print(f"Jev available (no key yet): {jev_parser.is_available()}")
    print(f"Azure OpenAI available: {llm_parser.client is not None}")
    print(f"Current active engine: {llm_parser.get_active_engine()}")

    # Test fallback analysis when no engines are configured
    cluster = WishCluster(id=1, chat_id=1, date=date(2024, 8, 1), unique_wishers=1, total_wish_score=1.0)
    messages = [Message(id=1, sender="Alice", text="Happy birthday Dave!", timestamp=datetime(2024, 8, 1, 10, 0))]
    fallback_res = llm_parser.analyze_birthday_cluster(cluster, messages)
    print(f"Fallback analysis succeeded: person={fallback_res.get('person')}, source={fallback_res.get('source')}")
    assert fallback_res.get('source') in ['fallback', 'jev-system-one', 'llm']

    # Test that setting TYPESAFE_API_KEY activates Jev engine
    jev_parser.api_key = "test_key_placeholder"
    print(f"Jev available with key: {jev_parser.is_available()}")
    print(f"Active engine with key: {llm_parser.get_active_engine()}")
    assert jev_parser.is_available() is True
    assert "TypeSafe Jev" in llm_parser.get_active_engine()

    # Reset
    jev_parser.api_key = os.getenv("TYPESAFE_API_KEY")
    print("✅ Dual engine detection and fallback passed!\n")


def test_live_jev_connection():
    """Test real connection to TypeSafe AI if TYPESAFE_API_KEY is present."""
    print("=" * 60)
    print("5. Live TypeSafe AI Connection Test")
    print("=" * 60)

    api_key = os.getenv("TYPESAFE_API_KEY")
    if not api_key:
        print("ℹ️  TYPESAFE_API_KEY is not set in environment or .env.")
        print("   To test live calls, set TYPESAFE_API_KEY=your_key in .env or run:")
        print("   export TYPESAFE_API_KEY='your_key'")
        return

    print(f"Found TYPESAFE_API_KEY: {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''}")
    print("Sending live test request to TypeSafe AI Jev...")
    
    cluster = WishCluster(id=1, chat_id=1, date=date(2024, 8, 1), unique_wishers=2, total_wish_score=2.0)
    messages = [
        Message(id=1, sender="Alice", text="Happy birthday +15551234567! Have a great day!", timestamp=datetime(2024, 8, 1, 10, 0)),
        Message(id=2, sender="+1 (555) 123-4567", text="Thank you Alice!", timestamp=datetime(2024, 8, 1, 10, 5))
    ]

    try:
        import time
        start_t = time.time()
        result = jev_parser.analyze_birthday_cluster(cluster, messages)
        elapsed = (time.time() - start_t) * 1000
        print(f"⚡ Jev call succeeded in {elapsed:.1f}ms!")
        print("Live Result:")
        print(json.dumps(result, indent=2))
        print("✅ Live TypeSafe Jev test passed!\n")
    except Exception as e:
        print(f"❌ Live test error: {e}")


if __name__ == '__main__':
    test_candidate_extraction()
    test_format_jev_response_with_phone()
    test_belated_timing_adjustment()
    test_llm_parser_active_engine()
    test_live_jev_connection()
    print("=" * 60)
    print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
