#!/usr/bin/env python3
"""
Test specific webhook import issues
"""

import os
import sys

# Add parent directory to path so backend module can be found
backend_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(backend_dir)
sys.path.insert(0, parent_dir)

print("Testing webhook imports...")

try:
    print("1. Testing booking.message_bus import...")
    from booking.message_bus import MessageBus
    print("✅ booking.message_bus import successful")
except ImportError as e:
    print(f"❌ booking.message_bus import failed: {e}")
    print(f"   Current directory: {os.getcwd()}")
    print(f"   Backend directory: {backend_dir}")
    print(f"   sys.path entries:")
    for i, path in enumerate(sys.path):
        print(f"     {i}: {path}")

try:
    print("\n2. Testing tasks.comment_intake import...")
    from tasks.comment_intake import process_comment_event
    print("✅ tasks.comment_intake import successful")
except ImportError as e:
    print(f"❌ tasks.comment_intake import failed: {e}")

try:
    print("\n3. Testing full webhooks module import...")
    from api.webhooks import router
    print("✅ api.webhooks import successful")
except ImportError as e:
    print(f"❌ api.webhooks import failed: {e}")

print("\nTest complete.")