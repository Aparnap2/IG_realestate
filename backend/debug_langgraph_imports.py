#!/usr/bin/env python3
"""
Debug script to identify exactly why LangGraph appears unavailable in production
"""
import sys
import os
import importlib.util
import traceback

def test_langgraph_import():
    """Test direct LangGraph import"""
    print("=== Testing Direct LangGraph Import ===")
    try:
        from langgraph import StateGraph, END
        from langgraph.checkpoint.redis import RedisSaver  
        from langgraph.types import Send, Command
        from langgraph.graph.message import add_messages
        print("✅ Direct LangGraph import: SUCCESS")
        print(f"  - StateGraph: {StateGraph}")
        print(f"  - add_messages: {add_messages}")
        return True
    except Exception as e:
        print(f"❌ Direct LangGraph import: FAILED - {e}")
        traceback.print_exc()
        return False

def test_module_imports():
    """Test the actual module imports that are failing"""
    print("\n=== Testing Module Imports ===")
    
    # Set up proper Python path
    current_dir = os.getcwd()
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    modules_to_test = [
        ('utils.llm_client', 'utils/llm_client.py'),
        ('automation.nurture_sequences', 'automation/nurture_sequences.py'),
        ('pipeline.universal_lead_processor', 'pipeline/universal_lead_processor.py')
    ]
    
    results = {}
    
    for module_name, file_path in modules_to_test:
        print(f"\n--- Testing {module_name} ---")
        try:
            # Try to import the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Check if LANGGRAPH_AVAILABLE is set correctly
            langgraph_available = getattr(module, 'LANGGRAPH_AVAILABLE', None)
            print(f"✅ {module_name} import: SUCCESS")
            print(f"   LANGGRAPH_AVAILABLE = {langgraph_available}")
            results[module_name] = {'success': True, 'langgraph_available': langgraph_available}
            
        except Exception as e:
            print(f"❌ {module_name} import: FAILED - {e}")
            print(f"   Error type: {type(e).__name__}")
            
            # Check if it's a relative import issue
            if "relative import" in str(e):
                print("   🔍 This is a RELATIVE IMPORT issue!")
                
            results[module_name] = {'success': False, 'error': str(e), 'error_type': type(e).__name__}
    
    return results

def analyze_import_errors():
    """Analyze the specific import errors"""
    print("\n=== Analyzing Import Structure ===")
    
    # Check the relative imports in each file
    files_to_check = [
        'utils/llm_client.py',
        'automation/nurture_sequences.py', 
        'pipeline/universal_lead_processor.py'
    ]
    
    for file_path in files_to_check:
        print(f"\n--- {file_path} ---")
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith('from .') or line.strip().startswith('from ..'):
                    print(f"  Line {i+1}: {line.strip()}")
                    print(f"    ^ RELATIVE IMPORT - This will fail when module is imported directly")
                    
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

def main():
    print("🔍 LangGraph Import Debug Analysis")
    print("=" * 50)
    
    # Test 1: Direct LangGraph import
    langgraph_works = test_langgraph_import()
    
    # Test 2: Module imports
    results = test_module_imports()
    
    # Test 3: Analyze relative imports
    analyze_import_errors()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print(f"LangGraph Direct Import: {'✅ WORKING' if langgraph_works else '❌ BROKEN'}")
    print("\nModule Import Results:")
    for module, result in results.items():
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        lang_status = f"(LangGraph: {result.get('langgraph_available', 'N/A')})"
        print(f"  {module}: {status} {lang_status}")
    
    print("\n🎯 CONCLUSION:")
    if langgraph_works:
        print("✅ LangGraph is available and working correctly")
        print("❌ The issue is RELATIVE IMPORTS in the modules")
        print("💡 Solution: Fix relative import structure or add proper error handling")
    else:
        print("❌ LangGraph is not properly available")
        print("💡 Solution: Install langgraph dependencies")

if __name__ == "__main__":
    main()