#!/usr/bin/env python3
"""
Test script to verify ICS calendar generation works.
"""

from app import generate_ics_calendar

def test_ics_generation():
    """Test ICS calendar generation with sample birthday data."""
    print("🧪 Testing ICS Calendar Generation...")
    
    # Sample birthday data
    test_birthdays = [
        {
            'name': 'Sarath',
            'month': 8,
            'day': 1,
            'confidence': 0.95
        },
        {
            'name': 'Keval',
            'month': 6,
            'day': 16,
            'confidence': 0.95
        },
        {
            'name': 'Divya',
            'month': 6,
            'day': 19,
            'confidence': 0.95
        }
    ]
    
    try:
        # Generate ICS content
        ics_content = generate_ics_calendar(test_birthdays)
        
        print("✅ ICS generation successful!")
        print(f"📄 Generated content length: {len(ics_content)} characters")
        
        # Show a preview
        lines = ics_content.split('\r\n')
        print("\n📋 ICS Preview (first 15 lines):")
        for i, line in enumerate(lines[:15]):
            print(f"   {i+1:2d}: {line}")
        
        if len(lines) > 15:
            print(f"   ... and {len(lines) - 15} more lines")
        
        # Save to file for testing
        with open('test_birthdays.ics', 'w', encoding='utf-8') as f:
            f.write(ics_content)
        
        print(f"\n💾 Test file saved as: test_birthdays.ics")
        print(f"📊 Total events created: {len(test_birthdays)}")
        
        # Validate basic structure
        required_elements = [
            'BEGIN:VCALENDAR',
            'END:VCALENDAR',
            'BEGIN:VEVENT',
            'END:VEVENT',
            'SUMMARY:🎂',
            'RRULE:FREQ=YEARLY'
        ]
        
        missing = [elem for elem in required_elements if elem not in ics_content]
        if missing:
            print(f"⚠️  Missing elements: {missing}")
            return False
        else:
            print("✅ All required ICS elements present")
            return True
            
    except Exception as e:
        print(f"❌ ICS generation failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing ICS Calendar Export Feature")
    print("=" * 50)
    
    success = test_ics_generation()
    
    if success:
        print("\n🎉 ICS export feature is working!")
        print("\n💡 How to test:")
        print("   1. Open the app in browser: http://127.0.0.1:5001")
        print("   2. Upload a WhatsApp file and view results")
        print("   3. Check/uncheck birthdays you want")
        print("   4. Click 'Export Calendar' button")
        print("   5. Import the downloaded .ics file into your calendar app")
        print("\n📅 The events will repeat yearly automatically!")
    else:
        print("\n❌ ICS export has issues - check the implementation")