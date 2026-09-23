#!/usr/bin/env python3
"""
Test script to verify the clustering improvements.
"""

from analyzer import BirthdayAnalyzer
from models import Message, MessageType
from datetime import datetime

def test_improved_clustering():
    """Test the improved clustering with stricter parameters."""
    print("🧪 Testing Improved Clustering...")
    
    analyzer = BirthdayAnalyzer()
    
    # Create test messages - simulating weak signals that should be filtered out
    weak_messages = [
        Message(
            id=1,
            sender="Alice", 
            text="🎂",  # Just emoji - should be rejected
            timestamp=datetime(2024, 8, 1, 10, 0),
            message_type=MessageType.NORMAL
        ),
        Message(
            id=2,
            sender="Bob",
            text="Party! 🎉",  # No birthday words - should be rejected
            timestamp=datetime(2024, 8, 1, 10, 30),
            message_type=MessageType.NORMAL
        ),
        Message(
            id=3,
            sender="Charlie",
            text="Hi",  # Too short - should be rejected
            timestamp=datetime(2024, 8, 1, 11, 0),
            message_type=MessageType.NORMAL
        ),
    ]
    
    # Create strong birthday messages that should pass
    strong_messages = [
        Message(
            id=4,
            sender="Alice",
            text="Happy birthday Sarath! Hope you have a wonderful day",
            timestamp=datetime(2024, 8, 1, 10, 0),
            message_type=MessageType.NORMAL
        ),
        Message(
            id=5,
            sender="Bob", 
            text="HBD Sarath! Many many happy returns of the day",
            timestamp=datetime(2024, 8, 1, 11, 0),
            message_type=MessageType.NORMAL
        ),
        Message(
            id=6,
            sender="Charlie",
            text="Wishing you a very happy birthday buddy! 🎂",
            timestamp=datetime(2024, 8, 1, 12, 0),
            message_type=MessageType.NORMAL
        ),
    ]
    
    print("\n📊 Testing Weak Messages (should be filtered out):")
    weak_wishes = analyzer.analyze_messages(weak_messages)
    print(f"   Weak wishes detected: {len(weak_wishes)} (expected: 0)")
    for wish in weak_wishes:
        msg = next(m for m in weak_messages if m.id == wish.message_id)
        print(f"   - '{msg.text}' (score: {wish.wish_score:.2f})")
    
    print("\n📊 Testing Strong Messages (should pass):")
    strong_wishes = analyzer.analyze_messages(strong_messages)
    print(f"   Strong wishes detected: {len(strong_wishes)} (expected: 3)")
    for wish in strong_wishes:
        msg = next(m for m in strong_messages if m.id == wish.message_id)
        print(f"   - '{msg.text}' (score: {wish.wish_score:.2f})")
    
    print("\n📊 Testing Clustering (strong messages only):")
    clusters = analyzer.cluster_wishes_by_date(strong_messages, strong_wishes, chat_id=1)
    print(f"   Clusters created: {len(clusters)} (expected: 1)")
    
    for cluster in clusters:
        print(f"   - Date: {cluster.date}")
        print(f"   - Wishers: {cluster.unique_wishers}")
        print(f"   - Total score: {cluster.total_wish_score:.2f}")
        print(f"   - Has mentions: {cluster.has_explicit_mentions}")
    
    # Test confidence calculation
    if clusters:
        confidence = analyzer.calculate_confidence(clusters[0])
        print(f"   - Confidence: {confidence:.2f}")
    
    print("\n✅ Clustering improvements test completed!")
    
    return len(weak_wishes) == 0 and len(strong_wishes) == 3 and len(clusters) == 1

if __name__ == "__main__":
    print("🚀 Testing Birthday Analyzer Improvements")
    print("=" * 50)
    
    success = test_improved_clustering()
    
    if success:
        print("\n🎉 All tests passed! Your improvements are working correctly.")
        print("\n💡 Key improvements implemented:")
        print("   ✅ Stricter clustering (16h window, min 2 wishers, 0.8 score threshold)")
        print("   ✅ Better filtering (requires strong birthday patterns + min 3 words)")
        print("   ✅ Simplified confidence calculation integrated into analyzer")
        print("   ✅ Max 2 clusters per day limit")
        print("\n📈 Expected result: 170 clusters → 5-15 quality clusters")
    else:
        print("\n❌ Some tests failed. Check the implementation.")