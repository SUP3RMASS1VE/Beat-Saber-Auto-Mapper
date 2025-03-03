#!/usr/bin/env python3
import os
import sys
import subprocess
import importlib.util

def check_requirements():
    """Check if all required packages are installed."""
    required_packages = ["gradio", "numpy"]
    missing_packages = []
    
    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Please run: pip install -r requirements.txt")
        return False
    
    return True

def check_julia():
    """Check if Julia is installed and accessible."""
    try:
        subprocess.run(["julia", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Julia is not installed or not in PATH.")
        print("Please install Julia from: https://julialang.org/downloads/")
        return False

def check_ffmpeg():
    """Check if FFmpeg is installed and accessible."""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        print("FFmpeg is not installed or not in PATH.")
        print("Please install FFmpeg from: https://ffmpeg.org/download.html")
        return False

def main():
    """Run the Beat Saber Automatic Mapper app."""
    # Check if requirements are met
    if not check_requirements() or not check_julia() or not check_ffmpeg():
        print("\nSome requirements are missing. Please install them and try again.")
        print("You can run setup.py to check and install requirements.")
        return 1
    
    # Create necessary directories
    os.makedirs("temp_uploads", exist_ok=True)
    os.makedirs("output_maps", exist_ok=True)
    
    # Run the app
    try:
        from app import app
        app.launch()
    except Exception as e:
        print(f"Error running the app: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 