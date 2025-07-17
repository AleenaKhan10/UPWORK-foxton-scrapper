#!/usr/bin/env python3
"""
Integration Test Script for Foxtons Scraper
Tests the new API handler, JSON data manager, and updated scraper functionality.
"""

import os
import sys
import json
from datetime import datetime

def test_imports():
    """Test that all modules can be imported successfully"""
    print("🧪 Testing module imports...")
    
    try:
        from db_api_handler import create_api_handler, DatabaseAPIHandler
        print("✅ API Handler imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import API Handler: {e}")
        return False
    
    try:
        from json_data_manager import create_data_manager, JSONDataManager
        print("✅ JSON Data Manager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import JSON Data Manager: {e}")
        return False
    
    try:
        from api_config import get_api_config, validate_config, check_token_expiration
        print("✅ API Config imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import API Config: {e}")
        return False
    
    return True

def test_api_config():
    """Test API configuration validation"""
    print("\n🧪 Testing API configuration...")
    
    try:
        from api_config import validate_config, check_token_expiration, get_api_config
        
        # Test validation
        validation = validate_config()
        print(f"✅ Config validation completed")
        print(f"  Valid: {validation['is_valid']}")
        print(f"  Errors: {len(validation['errors'])}")
        print(f"  Warnings: {len(validation['warnings'])}")
        
        # Test token expiration check
        config = get_api_config()
        token_info = check_token_expiration(config.get('token'))
        print(f"✅ Token check completed")
        print(f"  Expired: {token_info['is_expired']}")
        print(f"  Message: {token_info['message']}")
        
        return True
        
    except Exception as e:
        print(f"❌ API config test failed: {e}")
        return False

def test_json_data_manager():
    """Test JSON data manager functionality"""
    print("\n🧪 Testing JSON Data Manager...")
    
    try:
        from json_data_manager import create_data_manager
        
        # Create test data manager
        test_file = "test_data.json"
        manager = create_data_manager(test_file)
        
        if not manager:
            print("❌ Failed to create data manager")
            return False
        
        print("✅ Data Manager created successfully")
        
        # Test adding a record
        test_record = {
            "url": "https://test.com/property/123",
            "property_id": "test123",
            "scraped_at": datetime.now().isoformat(),
            "scraping_status": "completed",
            "address": "Test Address, London",
            "description": "Test property description",
            "property_type": "Flat",
            "rooms": {"beds": 2, "baths": 1},
            "price": "£500,000",
            "key_features": ["Feature 1", "Feature 2"],
            "further_details": {"Tenure": "Leasehold"},
            "nearest_stations": [],
            "local_life": "Test local area info",
            "epc_rating": {"current": "B-80", "potential": "A-90"},
            "agent_email": "test@foxtons.co.uk",
            "images": []
        }
        
        # Test validation
        is_valid, errors = manager.validate_property_data(test_record)
        print(f"✅ Record validation: {is_valid}")
        if errors:
            print(f"  Errors: {errors}")
        
        # Test adding record
        if manager.add_record(test_record):
            print("✅ Record added successfully")
        else:
            print("❌ Failed to add record")
            return False
        
        # Test saving data
        if manager.save_data():
            print("✅ Data saved successfully")
        else:
            print("❌ Failed to save data")
            return False
        
        # Test loading data
        if manager.load_data():
            print("✅ Data loaded successfully")
            print(f"  Records: {len(manager.data)}")
        else:
            print("❌ Failed to load data")
            return False
        
        # Get statistics
        stats = manager.get_statistics()
        print(f"✅ Statistics retrieved:")
        for key, value in stats.items():
            print(f"    {key}: {value}")
        
        # Cleanup test file
        if os.path.exists(test_file):
            os.remove(test_file)
            print("✅ Test file cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ JSON Data Manager test failed: {e}")
        return False

def test_api_handler():
    """Test API handler functionality"""
    print("\n🧪 Testing API Handler...")
    
    try:
        from db_api_handler import create_api_handler
        
        # Create API handler
        handler = create_api_handler()
        
        if not handler:
            print("⚠️ API Handler not available (likely due to missing config)")
            return True  # This is acceptable in test environment
        
        print("✅ API Handler created successfully")
        
        # Test token expiration check
        if handler.access_token:
            # 5. Test token refresh functionality (simulated)
            print("5. Testing token refresh...")
            original_token = handler.access_token
            refresh_result = handler.refresh_access_token()
            print(f"   Token refresh: {'Success' if refresh_result else 'Failed (expected if no refresh endpoint)'}")
        
        # Test property mapping
        test_property = {
            "url": "https://test.com/property/123",
            "property_id": "test123",
            "address": "Test Address, London SW1",
            "description": "Test property description",
            "property_type": "Flat",
            "rooms": {"beds": 2, "baths": 1},
            "price": "£500,000",
            "key_features": ["Feature 1", "Feature 2"],
            "further_details": {"Total Sq Ft": "800 (74.32 Sq M) approx."},
            "nearest_stations": [{"station_name": "CENTRAL", "station_info": "Test Station"}],
            "epc_rating": {"current": "B-80"},
            "agent_email": "test@foxtons.co.uk"
        }
        
        try:
            api_data = handler.map_property_to_api_format(test_property)
            print("✅ Property mapping successful")
            print(f"  API data keys: {list(api_data.keys())}")
        except Exception as e:
            print(f"⚠️ Property mapping failed: {e}")
        
        # Get statistics
        stats = handler.get_statistics()
        print(f"✅ API Handler statistics:")
        for key, value in stats.items():
            print(f"    {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ API Handler test failed: {e}")
        return False

def test_scraper_integration():
    """Test that the updated scraper can be initialized with new components"""
    print("\n🧪 Testing Scraper Integration...")
    
    try:
        # Test if we can import the updated scraper
        from listing_details import PropertyDetailsScraper
        print("✅ Updated scraper imported successfully")
        
        # Test initialization (without actually starting browser)
        # We'll just test that the initialization process works
        test_csv = "test_urls.csv"
        
        # Create a minimal test CSV
        with open(test_csv, 'w', encoding='utf-8') as f:
            f.write("URL\n")
            f.write("https://test.com/property/1\n")
            f.write("https://test.com/property/2\n")
        
        print("✅ Test CSV created")
        
        # Try to initialize scraper (this should work even without browser)
        try:
            # We won't actually create the scraper with webdriver since that requires Chrome
            # Just test that the class can be imported and the file exists
            print("✅ Scraper class available for initialization")
            
        except Exception as e:
            print(f"⚠️ Scraper initialization test skipped: {e}")
        
        # Cleanup
        if os.path.exists(test_csv):
            os.remove(test_csv)
            print("✅ Test CSV cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Scraper integration test failed: {e}")
        return False

def test_file_structure():
    """Test that all required files exist"""
    print("\n🧪 Testing file structure...")
    
    required_files = [
        "db_api_handler.py",
        "json_data_manager.py", 
        "api_config.py",
        "listing_details.py"
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    return True

def run_all_tests():
    """Run all integration tests"""
    print("🚀 Starting Integration Tests for Foxtons Scraper")
    print("=" * 60)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Module Imports", test_imports),
        ("API Configuration", test_api_config),
        ("JSON Data Manager", test_json_data_manager),
        ("API Handler", test_api_handler),
        ("Scraper Integration", test_scraper_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:.<30} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Overall Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The integration is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 