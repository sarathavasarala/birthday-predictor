#!/usr/bin/env python3
"""
Test script for Azure OpenAI integration.
Run this to verify your API key and endpoint are working.
"""

import os
import json
from llm_parser import llm_parser

def test_llm_connection():
    """Test basic Azure OpenAI connection."""
    print("Testing Azure OpenAI Connection...")
    print(f"LLM Available: {llm_parser.is_available()}")
    
    if not llm_parser.is_available():
        print("\n❌ Azure OpenAI not available. Please set environment variables:")
        print("   export AZURE_OPENAI_API_KEY='your-api-key'")
        print("   export AZURE_OPENAI_ENDPOINT='your-endpoint'")
        return False
    
    print(f"Deployment: {llm_parser.deployment_name}")
    print("✅ Azure OpenAI client initialized")
    
    # Test a simple API call
    try:
        from openai import AzureOpenAI
        
        client = AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version="2024-10-21",
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
        )
        
        print("\n🧪 Testing simple API call...")
        response = client.chat.completions.create(
            model=llm_parser.deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello! Just say 'API working' to confirm the connection."}
            ],
            max_tokens=20
        )
        
        result = response.choices[0].message.content
        print(f"✅ API Response: {result}")
        return True
        
    except Exception as e:
        print(f"❌ API Test Failed: {e}")
        return False

def test_birthday_analysis():
    """Test birthday message analysis."""
    if not llm_parser.is_available():
        print("❌ Skipping birthday analysis test - LLM not available")
        return
    
    print("\n🎂 Testing Birthday Analysis...")
    
    # Create mock cluster and messages for testing
    from models import WishMessage, WishCluster, Message
    from datetime import datetime, date
    
    # Create test messages
    test_messages = [
        Message(
            id=1,
            sender="Alice",
            text="Happy birthday Sarath! Hope you have a wonderful day 🎂",
            timestamp=datetime(2024, 8, 1, 10, 30)
        ),
        Message(
            id=2,
            sender="Bob", 
            text="HBD Sarath! Many many happy returns",
            timestamp=datetime(2024, 8, 1, 11, 15)
        ),
        Message(
            id=3,
            sender="Charlie",
            text="Sarath, wishing you a very happy birthday! +91 12345 67890",
            timestamp=datetime(2024, 8, 1, 12, 0)
        ),
        Message(
            id=4,
            sender="Sarath",
            text="Thank you everyone for the lovely wishes! 😊",
            timestamp=datetime(2024, 8, 1, 13, 30)
        )
    ]
    
    # Create test cluster
    test_cluster = WishCluster(
        id=1,
        chat_id=1,
        date=date(2024, 8, 1),
        unique_wishers=3,
        total_wish_score=3.0,
        has_thanks=True
    )
    
    try:
        # Test LLM analysis
        result = llm_parser.analyze_birthday_cluster(test_cluster, test_messages)
        
        print("✅ LLM Analysis Result:")
        print(json.dumps(result, indent=2, default=str))
        
        # Verify key fields
        expected_person = "Sarath"
        if result.get('person') == expected_person:
            print(f"✅ Correctly identified person: {expected_person}")
        else:
            print(f"⚠️  Person identification: expected '{expected_person}', got '{result.get('person')}'")
        
        if result.get('confidence', 0) > 50:
            print(f"✅ Good confidence: {result.get('confidence')}%")
        else:
            print(f"⚠️  Low confidence: {result.get('confidence')}%")
            
        return True
        
    except Exception as e:
        print(f"❌ Birthday analysis test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Azure OpenAI LLM Integration Test")
    print("=" * 50)
    
    # Test connection
    connection_ok = test_llm_connection()
    
    if connection_ok:
        # Test birthday analysis
        test_birthday_analysis()
        print("\n🎉 All tests completed!")
    else:
        print("\n💡 Set your Azure OpenAI credentials and try again:")
        print("   export AZURE_OPENAI_API_KEY='your-key-here'")
        print("   export AZURE_OPENAI_ENDPOINT='https://your-resource.openai.azure.com/'")