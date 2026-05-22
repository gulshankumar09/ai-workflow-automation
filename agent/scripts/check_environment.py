#!/usr/bin/env python3
"""
Environment Check Script for ai-workflow-automation Core

This script helps diagnose potential compatibility issues,
especially the Python 3.13 debugger issue with frozenlist.
"""

import sys
import os
import importlib.util
import structlog

# Add the core directory to Python path for app imports
core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

logger = get_logger(__name__)

def check_python_version():
    """Check Python version and warn about known issues."""
    version = sys.version_info
    print(f"🐍 Python Version: {version.major}.{version.minor}.{version.micro}")
    
    if version >= (3, 13):
        print("⚠️  Python 3.13 detected")
        if hasattr(sys, 'gettrace') and sys.gettrace():
            print("🐛 Debugger is attached - may cause frozenlist/_frozenlist.pyx errors")
            print("💡 Recommendation: Run without debugger for production")
        else:
            print("✅ No debugger attached - should work fine")
    else:
        print("✅ Python version compatible with all features")

def check_critical_imports():
    """Check if critical imports work."""
    imports_to_check = [
        ('structlog', 'structlog'),
        ('langchain_google_genai', 'langchain_google_genai'),
        ('aiohttp', 'aiohttp'),
        ('frozenlist', 'frozenlist'),
        ('langgraph', 'langgraph'),
        ('fastapi', 'fastapi'),
        ('supabase', 'supabase'),
    ]
    
    print("\n📦 Checking Critical Imports:")
    failed_imports = []
    
    for import_name, package_name in imports_to_check:
        try:
            importlib.import_module(import_name)
            print(f"✅ {package_name}")
        except ImportError as e:
            print(f"❌ {package_name}: {e}")
            failed_imports.append(package_name)
        except Exception as e:
            print(f"⚠️  {package_name}: {e}")
            failed_imports.append(package_name)
    
    return failed_imports

def check_app_imports():
    """Check if app-specific imports work."""
    print("\n🏗️  Checking App Imports:")
    app_imports = [
        'app.shared.config',
        'app.ai.factory',
        'app.ai.gemini',
        'app.infrastructure.database.providers.supabase',
    ]
    
    failed_imports = []
    
    for import_name in app_imports:
        try:
            importlib.import_module(import_name)
            print(f"✅ {import_name}")
        except ImportError as e:
            print(f"❌ {import_name}: {e}")
            failed_imports.append(import_name)
        except Exception as e:
            print(f"⚠️  {import_name}: {e}")
            failed_imports.append(import_name)
    
    return failed_imports

def main():
    """Run all environment checks."""
    print("🔍 ai-workflow-automation Core Environment Check")
    print("=" * 40)
    
    # Check Python version
    check_python_version()
    
    # Check critical imports
    failed_critical = check_critical_imports()
    
    # Check app imports
    failed_app = check_app_imports()
    
    # Summary
    print("\n📋 Summary:")
    if not failed_critical and not failed_app:
        print("✅ All checks passed! Environment is ready.")
    else:
        print("❌ Some issues detected:")
        if failed_critical:
            print(f"   Critical packages: {', '.join(failed_critical)}")
        if failed_app:
            print(f"   App modules: {', '.join(failed_app)}")
        
        print("\n💡 Solutions:")
        print("   1. Run 'uv sync' to ensure all dependencies are installed")
        print("   2. If using Python 3.13 with debugger, try running without debugger")
        print("   3. Check README.md for detailed troubleshooting")

if __name__ == "__main__":
    main() 