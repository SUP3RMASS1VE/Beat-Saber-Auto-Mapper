#!/usr/bin/env python3
import os
import subprocess
import sys
import platform
import tempfile
import shutil
import zipfile
import urllib.request
import tarfile

# Import Julia setup utilities
from julia_setup import check_julia_installation, ensure_julia_installation, setup_julia_packages

def check_command(command, name):
    """Check if a command is available."""
    # For FFmpeg, first check if it's in the PATH or local directories
    if command == "ffmpeg":
        # Get the current PATH
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        
        # Check if ffmpeg is in any of the PATH directories
        for path_dir in path_dirs:
            ffmpeg_path = os.path.join(path_dir, 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
            if os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK):
                print(f"✅ {name} is installed in PATH at {ffmpeg_path}")
                return True
                
        # Also check the current working directory and ffmpeg directory
        cwd = os.getcwd()
        ffmpeg_in_cwd = os.path.join(cwd, 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
        ffmpeg_in_dir = os.path.join(cwd, 'ffmpeg', 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
        
        if os.path.exists(ffmpeg_in_cwd) and os.access(ffmpeg_in_cwd, os.X_OK):
            print(f"✅ {name} is installed in current directory at {ffmpeg_in_cwd}")
            return True
        elif os.path.exists(ffmpeg_in_dir) and os.access(ffmpeg_in_dir, os.X_OK):
            print(f"✅ {name} is installed in ffmpeg directory at {ffmpeg_in_dir}")
            return True
            
        # Check common FFmpeg installation locations on Windows
        if platform.system() == 'Windows':
            common_locations = [
                "C:\\ffmpeg\\ffmpeg.exe",
                "C:\\Program Files\\ffmpeg\\ffmpeg.exe",
                os.path.join(os.environ.get('USERPROFILE', ''), 'ffmpeg', 'ffmpeg.exe')
            ]
            
            for location in common_locations:
                if os.path.exists(location) and os.access(location, os.X_OK):
                    print(f"✅ {name} is installed at {location}")
                    # Add to PATH for this session
                    ffmpeg_dir = os.path.dirname(location)
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
                    return True
    
    # Fall back to the command-line check
    try:
        subprocess.run([command, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"✅ {name} is installed")
        return True
    except FileNotFoundError:
        print(f"❌ {name} is not installed")
        return False

def install_ffmpeg():
    """Install FFmpeg automatically based on the platform."""
    system = platform.system().lower()
    
    print("Attempting to install FFmpeg automatically...")
    
    if system == "windows":
        return install_ffmpeg_windows()
    elif system == "darwin":  # macOS
        return install_ffmpeg_macos()
    elif system == "linux":
        return install_ffmpeg_linux()
    else:
        print(f"❌ Automatic FFmpeg installation not supported for {system}")
        return False

def install_ffmpeg_windows():
    """Install FFmpeg on Windows."""
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        ffmpeg_zip = os.path.join(temp_dir, "ffmpeg.zip")
        
        # Download FFmpeg
        print("Downloading FFmpeg for Windows...")
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        urllib.request.urlretrieve(url, ffmpeg_zip)
        
        # Extract the zip file
        print("Extracting FFmpeg...")
        with zipfile.ZipFile(ffmpeg_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find the ffmpeg directory (the first directory containing ffmpeg.exe)
        ffmpeg_source_dir = None
        for root, dirs, files in os.walk(temp_dir):
            if "ffmpeg.exe" in files:
                ffmpeg_source_dir = root
                break
        
        if not ffmpeg_source_dir:
            print("❌ Could not find FFmpeg executables in the extracted files")
            return False
        
        # Create FFmpeg directory in the application folder
        ffmpeg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg")
        os.makedirs(ffmpeg_dir, exist_ok=True)
        
        # Copy FFmpeg executables
        for file in os.listdir(ffmpeg_source_dir):
            if file.endswith(".exe"):
                shutil.copy2(os.path.join(ffmpeg_source_dir, file), ffmpeg_dir)
        
        # Add to PATH for the current process
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
        
        # Check if it works
        if check_command(os.path.join(ffmpeg_dir, "ffmpeg"), "FFmpeg"):
            print(f"✅ FFmpeg installed successfully to {ffmpeg_dir}")
            print("NOTE: FFmpeg is installed locally in the application directory.")
            return True
        else:
            print("❌ FFmpeg installation failed")
            return False
    except Exception as e:
        print(f"❌ Error installing FFmpeg: {str(e)}")
        return False
    finally:
        # Clean up
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

def install_ffmpeg_macos():
    """Install FFmpeg on macOS using Homebrew."""
    try:
        # Check if Homebrew is installed
        if not check_command("brew", "Homebrew"):
            print("Installing Homebrew...")
            brew_install_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            subprocess.run(brew_install_cmd, shell=True, check=True)
        
        # Install FFmpeg
        print("Installing FFmpeg via Homebrew...")
        subprocess.run(["brew", "install", "ffmpeg"], check=True)
        
        return check_command("ffmpeg", "FFmpeg")
    except Exception as e:
        print(f"❌ Error installing FFmpeg: {str(e)}")
        return False

def install_ffmpeg_linux():
    """Install FFmpeg on Linux."""
    try:
        # Detect package manager
        if shutil.which("apt"):
            print("Installing FFmpeg via apt...")
            subprocess.run(["sudo", "apt", "update"], check=True)
            subprocess.run(["sudo", "apt", "install", "-y", "ffmpeg"], check=True)
        elif shutil.which("dnf"):
            print("Installing FFmpeg via dnf...")
            subprocess.run(["sudo", "dnf", "install", "-y", "ffmpeg"], check=True)
        elif shutil.which("yum"):
            print("Installing FFmpeg via yum...")
            subprocess.run(["sudo", "yum", "install", "-y", "ffmpeg"], check=True)
        elif shutil.which("pacman"):
            print("Installing FFmpeg via pacman...")
            subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "ffmpeg"], check=True)
        else:
            print("❌ Could not detect package manager. Please install FFmpeg manually.")
            return False
        
        return check_command("ffmpeg", "FFmpeg")
    except Exception as e:
        print(f"❌ Error installing FFmpeg: {str(e)}")
        return False

def main():
    """Check and set up the environment."""
    print("Checking requirements...")
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        print(f"❌ Python 3.7+ is required, but you have {python_version.major}.{python_version.minor}")
        return False
    else:
        print(f"✅ Python {python_version.major}.{python_version.minor} is installed")
    
    # Check Julia
    julia_path = check_julia_installation()
    if julia_path:
        print(f"✅ Julia is installed at: {julia_path}")
    else:
        print("❌ Julia is not installed. Attempting to install...")
        julia_path = ensure_julia_installation()
        if not julia_path:
            print("❌ Failed to install Julia. Please install it manually.")
            print("   Visit https://julialang.org/downloads/ for installation instructions.")
            return False
        else:
            print(f"✅ Julia installed successfully at: {julia_path}")
    
    # Check FFmpeg in PATH and common locations
    print("Checking for FFmpeg in PATH and common locations...")
    ffmpeg_ok = check_command("ffmpeg", "FFmpeg")
    if not ffmpeg_ok:
        print("FFmpeg not found in any standard location. Attempting to install FFmpeg automatically...")
        ffmpeg_ok = install_ffmpeg()
        if ffmpeg_ok:
            print("✅ FFmpeg installed successfully")
        else:
            print("⚠️ FFmpeg installation failed. Some features may not work correctly.")
            print("   Please install FFmpeg manually from https://ffmpeg.org/download.html")
    
    # Create directories
    os.makedirs("temp_uploads", exist_ok=True)
    os.makedirs("output_maps", exist_ok=True)
    print("✅ Created necessary directories")
    
    # Install Python dependencies
    print("Installing Python dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Python dependencies installed")
    
    # Set up Julia environment if Julia is installed
    if julia_path:
        print("Setting up Julia environment...")
        try:
            if setup_julia_packages(julia_path):
                print("✅ Julia environment set up")
            else:
                print("❌ Failed to set up Julia environment")
                return False
        except Exception as e:
            print(f"❌ Error setting up Julia environment: {str(e)}")
            return False
    
    # Print summary
    print("\nSetup Summary:")
    if not julia_path:
        print("❌ Julia is not installed. Please install it from https://julialang.org/downloads/")
    if not ffmpeg_ok:
        print("❌ FFmpeg installation failed. Please install it manually from https://ffmpeg.org/download.html")
    
    if julia_path and ffmpeg_ok:
        print("\n✅ Setup complete! You can now run the app with:")
        print("   python app.py")
    else:
        print("\n❌ Setup incomplete. Please install the missing requirements and run this script again.")
    
    return julia_path and ffmpeg_ok

if __name__ == "__main__":
    main() 