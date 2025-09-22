#!/usr/bin/env python3
"""
Script to apply database migrations
"""
import os
import sys
from alembic.config import Config
from alembic import command

def apply_migrations():
    """Apply all pending migrations"""
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create Alembic config
    alembic_cfg = Config(os.path.join(script_dir, "alembic.ini"))
    
    # Apply migrations
    try:
        command.upgrade(alembic_cfg, "head")
        print("Migrations applied successfully!")
    except Exception as e:
        print(f"Error applying migrations: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_migrations()