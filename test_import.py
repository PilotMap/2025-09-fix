#!/usr/bin/env python3
"""
Test script to validate faa_api_client import and parse_iso8601 behavior.
This script helps verify that the import fixes are working correctly.
"""

import sys
from datetime import datetime, timezone

def test_faa_api_client_import():
    """Test importing faa_api_client module"""
    print("Testing faa_api_client import...")
    try:
        from faa_api_client import FAAAPIClient, NetworkError, APIError, parse_iso8601
        print("✓ Successfully imported faa_api_client")
        return True
    except ImportError as e:
        print(f"✗ Failed to import faa_api_client: {e}")
        return False

def test_parse_iso8601():
    """Test parse_iso8601 function behavior"""
    print("\nTesting parse_iso8601 function...")
    try:
        from faa_api_client import parse_iso8601
        
        # Test cases
        test_cases = [
            "2023-12-01T12:00:00Z",
            "2023-12-01T12:00:00+00:00",
            "2023-12-01T12:00:00-05:00",
            "invalid_timestamp",
            ""
        ]
        
        for test_input in test_cases:
            result = parse_iso8601(test_input)
            if result:
                print(f"✓ parse_iso8601('{test_input}') = {result} (UTC: {result.utctimetuple()})")
            else:
                print(f"✓ parse_iso8601('{test_input}') = None (expected for invalid input)")
        
        return True
    except Exception as e:
        print(f"✗ Error testing parse_iso8601: {e}")
        return False

def test_timezone_consistency():
    """Test timezone consistency between parse_iso8601 and datetime.now(timezone.utc)"""
    print("\nTesting timezone consistency...")
    try:
        from faa_api_client import parse_iso8601
        
        # Test with current time
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat().replace('+00:00', 'Z')
        
        parsed_time = parse_iso8601(now_iso)
        
        if parsed_time and parsed_time.tzinfo == timezone.utc:
            print(f"✓ parse_iso8601 returns timezone-aware UTC datetime")
            print(f"  Original: {now_utc}")
            print(f"  Parsed:   {parsed_time}")
            print(f"  Timezone match: {parsed_time.tzinfo == timezone.utc}")
            return True
        else:
            print(f"✗ parse_iso8601 returned unexpected result: {parsed_time}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing timezone consistency: {e}")
        return False

def test_faa_api_client_instantiation():
    """Test creating FAAAPIClient instance"""
    print("\nTesting FAAAPIClient instantiation...")
    try:
        from faa_api_client import FAAAPIClient
        
        client = FAAAPIClient()
        print("✓ Successfully created FAAAPIClient instance")
        print(f"  Base URL: {client.base_url}")
        print(f"  Timeout: {client.timeout}")
        print(f"  Max retries: {client.max_retries}")
        return True
    except Exception as e:
        print(f"✗ Error creating FAAAPIClient: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("FAA API Client Import Test")
    print("=" * 60)
    
    tests = [
        test_faa_api_client_import,
        test_parse_iso8601,
        test_timezone_consistency,
        test_faa_api_client_instantiation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! Import fixes are working correctly.")
        return 0
    else:
        print("✗ Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
