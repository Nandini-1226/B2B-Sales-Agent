#!/usr/bin/env python3
"""
B2B Sales Agent Setup Script
This script helps you set up and run the B2B Sales Agent MVP.
"""

import os
import sys
import subprocess
import time

def check_python_version():
    """Check if Python version is suitable."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def install_requirements():
    """Install Python requirements."""
    print("📦 Installing Python requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install requirements")
        return False

def check_environment():
    """Check environment variables."""
    required_vars = ["DATABASE_URL", "GEMINI_API_KEY"]
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print("❌ Missing environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nSet them like this:")
        print('$Env:DATABASE_URL = "postgresql://user:pass@localhost:5432/sales_agent"')
        print('$Env:GEMINI_API_KEY = "your-gemini-api-key"')
        return False
    else:
        print("✅ Environment variables configured")
        return True

def run_setup():
    """Run the complete setup."""
    print("🛒 B2B Sales Agent Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install requirements
    if not install_requirements():
        return False
    
    # Check environment
    if not check_environment():
        return False
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Make sure PostgreSQL is running")
    print("2. Make sure Elasticsearch is running (optional)")
    print("3. Run: python run.py")
    print("\nOr run components separately:")
    print("- Backend: python -m uvicorn backend.main:app --reload")
    print("- Frontend: streamlit run frontend/chat_interface.py")
    
    return True

if __name__ == "__main__":
    run_setup()