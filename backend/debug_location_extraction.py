#!/usr/bin/env python3
"""
Debug script to test location extraction logic for real estate messages
"""
import re
import sys
import os

# Add current directory to path
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def test_location_extraction():
    """Test location extraction with various real estate messages"""
    
    # Import the extraction logic
    from utils.enhanced_llm_extraction import AgenticExtractionCoordinator, RuleBasedExtractor
    
    # Create coordinator
    coordinator = AgenticExtractionCoordinator()
    
    # Test messages
    test_messages = [
        "i need ASAP , miami beach , 250k dollar 4bhk condo",
        "looking for 4bhk condo in miami beach under 250k",
        "need house in california for 500k",
        "searching for 2 bed apartment near new york",
        "want property in orlando florida"
    ]
    
    print("🔍 Testing Location Extraction Logic")
    print("=" * 50)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n--- Test {i}: '{message}' ---")
        
        # Test the coordinator's extraction
        try:
            result = coordinator.coordinate_extraction(message)
            location = result.get('location', None)
            print(f"✅ AgenticExtractionCoordinator: location = '{location}'")
        except Exception as e:
            print(f"❌ AgenticExtractionCoordinator: {e}")
        
        # Test the rule-based extractor
        try:
            rule_extractor = RuleBasedExtractor()
            result = rule_extractor.extract_information(message)
            print(f"✅ RuleBasedExtractor: location = '{result.location}'")
        except Exception as e:
            print(f"❌ RuleBasedExtractor: {e}")

def analyze_pattern_matching():
    """Analyze the current pattern matching logic"""
    
    print("\n" + "=" * 50)
    print("🔍 Analyzing Pattern Matching Logic")
    print("=" * 50)
    
    message = "i need ASAP , miami beach , 250k dollar 4bhk condo"
    message_lower = message.lower()
    
    print(f"Test message: '{message}'")
    print(f"Message (lower): '{message_lower}'")
    
    # Test known locations check
    known_locations = [
        'california', 'florida', 'texas', 'new york', 'illinois', 'pennsylvania',
        'ohio', 'georgia', 'north carolina', 'michigan', 'new jersey', 'virginia',
        'washington', 'arizona', 'massachusetts', 'tennessee', 'indiana', 'maryland',
        'missouri', 'wisconsin', 'colorado', 'minnesota', 'south carolina', 'alabama',
        'louisiana', 'kentucky', 'oregon', 'oklahoma', 'connecticut', 'utah',
        'miami', 'orlando', 'tampa', 'jacksonville', 'los angeles', 'san francisco',
        'san diego', 'sacramento', 'oakland', 'fresno', 'bakersfield', 'riverside',
        'new york city', 'manhattan', 'brooklyn', 'queens', 'bronx', 'staten island',
        'chicago', 'houston', 'philadelphia', 'phoenix', 'san antonio', 'san diego',
        'dallas', 'san jose', 'austin', 'jacksonville', 'fort worth', 'columbus'
    ]
    
    print("\n--- Known Locations Check ---")
    for location in known_locations:
        if location in message_lower:
            print(f"✅ Found exact match: '{location}'")
            break
    else:
        print("❌ No exact match found in known locations")
    
    # Test pattern matching
    print("\n--- Pattern Matching Check ---")
    location_patterns = [
        r'(?:near|in|around|at|to)\s+([a-zA-Z\s]+?)(?:\s+(?:california|florida|texas|new\s+york|miami|orlando|tampa|london|canada|australia))?(?:\s|$|,)',
        r'(?:located|live|living)\s+(?:in|near|around)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
        r'([a-zA-Z\s]{3,25})\s+(?:area|region|county|city|state)',
        r'(?:looking|searching)\s+(?:in|near|around)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
    ]
    
    for i, pattern in enumerate(location_patterns, 1):
        match = re.search(pattern, message_lower)
        if match:
            location = match.group(1).strip().title()
            print(f"✅ Pattern {i} matched: '{location}'")
        else:
            print(f"❌ Pattern {i} no match")

def test_improved_extraction():
    """Test improved location extraction logic"""
    
    print("\n" + "=" * 50)
    print("🚀 Testing Improved Extraction Logic")
    print("=" * 50)
    
    def improved_extract_location(message: str) -> str:
        """Improved location extraction with better pattern matching"""
        message_lower = message.lower()
        
        # Enhanced known locations (including compound locations)
        known_locations = {
            # Single cities
            'miami': 'Miami',
            'miami beach': 'Miami Beach',
            'california': 'California',
            'florida': 'Florida',
            'new york': 'New York',
            'los angeles': 'Los Angeles',
            'san francisco': 'San Francisco',
            'chicago': 'Chicago',
            'houston': 'Houston',
            # Major compounds
            'new york city': 'New York City',
            'manhattan': 'Manhattan',
            'south beach': 'South Beach',
            # States
            'california': 'California',
            'florida': 'Florida',
            'texas': 'Texas',
        }
        
        # Check for compound locations first (longer matches)
        for location_key in sorted(known_locations.keys(), key=len, reverse=True):
            if location_key in message_lower:
                return known_locations[location_key]
        
        # Fallback to pattern matching
        location_patterns = [
            r'(?:near|in|around|at|to|of)\s+([a-zA-Z\s]+?)(?:\s+(?:california|florida|texas|new\s+york|miami|beach|orlando|tampa|london|canada|australia))?(?:\s|$|,)',
            r'(?:located|live|living)\s+(?:in|near|around)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            r'([a-zA-Z\s]{3,30})\s+(?:area|region|county|city|state|beach|district)',
            r'(?:looking|searching)\s+(?:in|near|around|for)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            # Pattern for location-name combinations
            r'([a-zA-Z\s]+?\s+[a-zA-Z\s]+?)(?:\s|$|,)',  # Two-word locations
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message_lower)
            if match:
                location = match.group(1).strip().title()
                # Clean up common prefixes/suffixes
                location = re.sub(r'^(?:the|a|an|any|house|budget|property|option|about|for|to|of)\s+', '', location)
                location = re.sub(r'(?:\s+(?:area|region|county|city|state|beach|district))+$', '', location)
                location = location.strip()
                
                # Validate location
                if (len(location) >= 3 and 
                    location.lower() not in ['the', 'house', 'budget', 'property', 'option', 'area', 'region', 'location'] and
                    not re.match(r'^\d+$', location)):
                    return location
        
        return None
    
    # Test with problematic message
    test_message = "i need ASAP , miami beach , 250k dollar 4bhk condo"
    
    print(f"Test message: '{test_message}'")
    result = improved_extract_location(test_message)
    print(f"✅ Improved extraction result: '{result}'")

def main():
    print("🏠 Real Estate Location Extraction Debug")
    print("=" * 60)
    
    # Test current extraction
    test_location_extraction()
    
    # Analyze pattern matching
    analyze_pattern_matching()
    
    # Test improved logic
    test_improved_extraction()
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("The main issues identified:")
    print("1. 'Miami Beach' is not in the exact match list (only 'miami' is)")
    print("2. Pattern matching doesn't capture compound locations well")
    print("3. Need better handling of location-name combinations")
    print("\n💡 SOLUTION: Implement improved extraction logic with compound locations")

if __name__ == "__main__":
    main()