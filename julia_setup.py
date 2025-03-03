#!/usr/bin/env python3
import os
import sys
import subprocess
import platform
import tempfile
import shutil
import urllib.request
import tarfile
import zipfile
from pathlib import Path
import gradio as gr

# Julia version to install
JULIA_VERSION = "1.8.5"

# URLs for Julia downloads
JULIA_URLS = {
    "Windows": {
        "x64": f"https://julialang-s3.julialang.org/bin/winnt/x64/{JULIA_VERSION.rsplit('.', 1)[0]}/julia-{JULIA_VERSION}-win64.exe",
        "x86": f"https://julialang-s3.julialang.org/bin/winnt/x86/{JULIA_VERSION.rsplit('.', 1)[0]}/julia-{JULIA_VERSION}-win32.exe"
    },
    "Linux": {
        "x64": f"https://julialang-s3.julialang.org/bin/linux/x64/{JULIA_VERSION.rsplit('.', 1)[0]}/julia-{JULIA_VERSION}-linux-x86_64.tar.gz",
        "aarch64": f"https://julialang-s3.julialang.org/bin/linux/aarch64/{JULIA_VERSION.rsplit('.', 1)[0]}/julia-{JULIA_VERSION}-linux-aarch64.tar.gz"
    },
    "Darwin": {
        "x64": f"https://julialang-s3.julialang.org/bin/mac/x64/{JULIA_VERSION.rsplit('.', 1)[0]}/julia-{JULIA_VERSION}-mac64.dmg",
        "arm64": f"https://julialang-s3.julialang.org/bin/mac/aarch64/{JULIA_VERSION.rsplit('.', 1)[0]}/julia-{JULIA_VERSION}-macaarch64.dmg"
    }
}

def get_julia_path():
    """Get the path to the Julia executable."""
    # Check if Julia is already in PATH
    try:
        result = subprocess.run(["julia", "--version"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        if result.returncode == 0 and "julia" in result.stdout.lower():
            return "julia"  # Julia is in PATH
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    
    # Check for Julia in common installation locations
    common_paths = []
    
    if platform.system() == "Windows":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        
        common_paths = [
            os.path.join(program_files, "Julia", "bin", "julia.exe"),
            os.path.join(program_files_x86, "Julia", "bin", "julia.exe"),
        ]
    elif platform.system() == "Darwin":  # macOS
        common_paths = [
            "/Applications/Julia-1.8.app/Contents/Resources/julia/bin/julia",
            "/Applications/Julia-1.7.app/Contents/Resources/julia/bin/julia",
            "/Applications/Julia-1.6.app/Contents/Resources/julia/bin/julia",
            "/usr/local/bin/julia",
        ]
    else:  # Linux and others
        common_paths = [
            "/usr/bin/julia",
            "/usr/local/bin/julia",
            "/opt/julia/bin/julia",
        ]
    
    # Add user-installed Julia
    home = str(Path.home())
    if platform.system() == "Windows":
        common_paths.append(os.path.join(home, "AppData", "Local", "Programs", "Julia", "bin", "julia.exe"))
    else:
        common_paths.append(os.path.join(home, ".julia", "bin", "julia"))
    
    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    
    return None

def check_julia_installation():
    """Check if Julia is installed and accessible."""
    julia_path = get_julia_path()
    if julia_path:
        try:
            result = subprocess.run([julia_path, "--version"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)
            if result.returncode == 0:
                print(f"Julia found at: {julia_path}")
                print(f"Julia version: {result.stdout.strip()}")
                return julia_path
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    
    return None

def download_file(url, target_path, progress=None):
    """Download a file with progress reporting."""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {e}")
            print(description)
    
    update_progress(0, f"Downloading from {url}")
    
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        with urllib.request.urlopen(url) as response:
            file_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            block_size = 8192
            
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                
                downloaded += len(buffer)
                temp_file.write(buffer)
                
                if file_size:
                    progress_value = min(downloaded / file_size, 1.0)
                    update_progress(progress_value, f"Downloaded {downloaded/1024/1024:.1f} MB of {file_size/1024/1024:.1f} MB")
        
        temp_file.close()
        shutil.move(temp_file.name, target_path)
        update_progress(1, "Download complete")
        return target_path
    except Exception as e:
        os.unlink(temp_file.name)
        update_progress(0, f"Error downloading: {str(e)}")
        raise

def install_julia_windows(progress=None):
    """Install Julia on Windows."""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {e}")
            print(description)
    
    update_progress(0.1, "Preparing to install Julia on Windows")
    
    # Determine architecture
    arch = "x64" if platform.machine().endswith('64') else "x86"
    url = JULIA_URLS["Windows"][arch]
    
    # Download the installer
    installer_path = os.path.join(tempfile.gettempdir(), f"julia-{JULIA_VERSION}-installer.exe")
    download_file(url, installer_path, progress)
    
    update_progress(0.5, "Running Julia installer. Please follow the installation prompts.")
    
    # Run the installer
    try:
        subprocess.run([installer_path], check=True)
        update_progress(1.0, "Julia installation completed. Please restart the application.")
        return True
    except subprocess.SubprocessError as e:
        update_progress(0, f"Error running installer: {str(e)}")
        return False

def install_julia_linux(progress=None):
    """Install Julia on Linux."""
    if progress:
        progress(0, "Preparing to install Julia on Linux")
    
    # Determine architecture
    arch = "x64" if platform.machine().endswith('64') else "aarch64" if platform.machine() == "aarch64" else None
    if not arch:
        if progress:
            progress(0, f"Unsupported architecture: {platform.machine()}")
        return False
    
    url = JULIA_URLS["Linux"][arch]
    
    # Download the tarball
    tarball_path = os.path.join(tempfile.gettempdir(), f"julia-{JULIA_VERSION}.tar.gz")
    download_file(url, tarball_path, progress)
    
    if progress:
        progress(0.5, "Extracting Julia")
    
    # Extract to user's home directory
    julia_dir = os.path.join(str(Path.home()), ".julia")
    os.makedirs(julia_dir, exist_ok=True)
    
    try:
        with tarfile.open(tarball_path) as tar:
            tar.extractall(path=julia_dir)
        
        # Find the extracted directory
        extracted_dirs = [d for d in os.listdir(julia_dir) if d.startswith("julia-")]
        if not extracted_dirs:
            if progress:
                progress(0, "Could not find extracted Julia directory")
            return False
        
        extracted_dir = os.path.join(julia_dir, extracted_dirs[0])
        julia_bin_dir = os.path.join(julia_dir, "bin")
        
        # Create bin directory and symlink
        os.makedirs(julia_bin_dir, exist_ok=True)
        julia_bin = os.path.join(extracted_dir, "bin", "julia")
        julia_symlink = os.path.join(julia_bin_dir, "julia")
        
        if os.path.exists(julia_symlink):
            os.remove(julia_symlink)
        
        os.symlink(julia_bin, julia_symlink)
        
        # Add to PATH in .bashrc or .zshrc
        shell_rc = os.path.join(str(Path.home()), ".bashrc")
        if os.path.exists(os.path.join(str(Path.home()), ".zshrc")):
            shell_rc = os.path.join(str(Path.home()), ".zshrc")
        
        with open(shell_rc, "a") as f:
            f.write(f"\n# Added by BeatSaber.jl installer\nexport PATH=\"{julia_bin_dir}:$PATH\"\n")
        
        if progress:
            progress(1, f"Julia installed to {extracted_dir}. Please restart your terminal or run: export PATH=\"{julia_bin_dir}:$PATH\"")
        
        return julia_bin
    except Exception as e:
        if progress:
            progress(0, f"Error installing Julia: {str(e)}")
        return False

def install_julia_macos(progress=None):
    """Install Julia on macOS."""
    if progress:
        progress(0, "Preparing to install Julia on macOS")
    
    # Determine architecture
    arch = "arm64" if platform.machine() == "arm64" else "x64"
    url = JULIA_URLS["Darwin"][arch]
    
    # Download the DMG
    dmg_path = os.path.join(tempfile.gettempdir(), f"julia-{JULIA_VERSION}.dmg")
    download_file(url, dmg_path, progress)
    
    if progress:
        progress(0.5, "Mounting Julia DMG")
    
    try:
        # Mount the DMG
        mount_process = subprocess.run(["hdiutil", "attach", dmg_path], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE, 
                                      text=True)
        
        # Find the mount point
        mount_point = None
        for line in mount_process.stdout.splitlines():
            if "/Volumes/Julia" in line:
                mount_point = line.split()[-1]
                break
        
        if not mount_point:
            if progress:
                progress(0, "Could not find Julia volume mount point")
            return False
        
        if progress:
            progress(0.7, "Installing Julia")
        
        # Copy the .app to Applications
        app_path = os.path.join(mount_point, "Julia-1.8.app")
        subprocess.run(["cp", "-R", app_path, "/Applications/"], check=True)
        
        # Create a symlink
        julia_bin = f"/Applications/Julia-{JULIA_VERSION.rsplit('.', 1)[0]}.app/Contents/Resources/julia/bin/julia"
        julia_symlink = "/usr/local/bin/julia"
        
        subprocess.run(["sudo", "ln", "-sf", julia_bin, julia_symlink], check=True)
        
        # Unmount the DMG
        subprocess.run(["hdiutil", "detach", mount_point], check=True)
        
        if progress:
            progress(1, "Julia installation completed")
        
        return julia_bin
    except subprocess.SubprocessError as e:
        if progress:
            progress(0, f"Error installing Julia: {str(e)}")
        return False

def install_julia(progress=None):
    """Install Julia based on the current platform."""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {e}")
            print(description)
    
    system = platform.system()
    
    update_progress(0.1, f"Preparing to install Julia on {system}")
    
    if system == "Windows":
        return install_julia_windows(progress)
    elif system == "Linux":
        return install_julia_linux(progress)
    elif system == "Darwin":  # macOS
        return install_julia_macos(progress)
    else:
        update_progress(0, f"Unsupported platform: {system}")
        return False

def setup_julia_packages(julia_path, progress=None):
    """Set up the required Julia packages."""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {str(e)}")
            print(description)
    
    update_progress(0.1, "Setting up Julia packages")
    
    try:
        # First, make sure essential packages are installed directly
        update_progress(0.2, "Installing essential Julia packages")
        essential_packages = ["WAV", "FFTW", "DSP", "JSON"]
        
        for i, package in enumerate(essential_packages):
            progress_value = 0.2 + (i / len(essential_packages) * 0.3)
            update_progress(progress_value, f"Installing {package} package")
            
            # Install package directly using Julia's Pkg
            cmd = [
                julia_path, 
                "-e", 
                f'using Pkg; Pkg.add("{package}")'
            ]
            
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            if result.returncode != 0:
                update_progress(0, f"Error installing {package}: {result.stderr}")
                print(f"Error installing {package}: {result.stderr}")
                # Continue with other packages
        
        # Run the setup script
        update_progress(0.5, "Running setup script")
        setup_script = os.path.join("src", "setup.jl")
        if not os.path.exists(setup_script):
            update_progress(0, f"Setup script not found: {setup_script}")
            return False
        
        update_progress(0.6, "Installing Julia packages (this may take a while)")
        
        result = subprocess.run([julia_path, setup_script], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        
        if result.returncode != 0:
            update_progress(0, f"Error setting up Julia packages: {result.stderr}")
            return False
        
        update_progress(1.0, "Julia packages installed successfully")
        
        return True
    except Exception as e:
        update_progress(0, f"Error setting up Julia packages: {str(e)}")
        return False

def setup_pyjulia(julia_path, progress=None):
    """Set up PyJulia to interface with Julia from Python."""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {e}")
            print(description)
    
    update_progress(0.1, "Setting up PyJulia")
    
    try:
        # Install PyJulia
        import julia
        julia.install()
        
        # Configure PyJulia to use the installed Julia
        os.environ["JULIA_EXECUTABLE"] = julia_path
        
        # Test PyJulia
        from julia import Main
        Main.eval('println("PyJulia is working!")')
        
        update_progress(1.0, "PyJulia set up successfully")
        
        return True
    except Exception as e:
        update_progress(0, f"Error setting up PyJulia: {str(e)}")
        return False

def ensure_julia_installation(progress=None):
    """Ensure Julia is installed and set up."""
    # Check if Julia is already installed
    julia_path = check_julia_installation()
    
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {e}")
            print(description)
    
    if not julia_path:
        update_progress(0.1, "Julia not found. Installing Julia...")
        
        # Install Julia
        julia_path = install_julia(progress)
        
        if not julia_path:
            update_progress(0, "Failed to install Julia")
            return None
    
    # Set up Julia packages
    update_progress(0.4, "Setting up Julia packages...")
    if not setup_julia_packages(julia_path, progress):
        update_progress(0, "Failed to set up Julia packages")
        return None
    
    # Set up PyJulia
    update_progress(0.7, "Setting up PyJulia...")
    if not setup_pyjulia(julia_path, progress):
        update_progress(0, "Failed to set up PyJulia")
        return None
    
    update_progress(1.0, "Julia installation complete!")
    return julia_path

def julia_installation_ui():
    """Create a Gradio UI for Julia installation."""
    with gr.Blocks(title="Julia Installation") as app:
        gr.Markdown("# Julia Installation")
        
        with gr.Row():
            with gr.Column():
                status_output = gr.Textbox(label="Status", value="Checking Julia installation...", interactive=False)
                install_button = gr.Button("Install Julia")
                setup_button = gr.Button("Set up Julia Packages")
            
            with gr.Column():
                progress_output = gr.Textbox(label="Progress", value="", interactive=False)
                progress_bar = gr.Slider(minimum=0, maximum=1, value=0, label="Progress", interactive=False)
        
        def check_julia():
            julia_path = check_julia_installation()
            if julia_path:
                return f"Julia is installed at: {julia_path}"
            else:
                return "Julia is not installed or not found in PATH"
        
        def install_julia_ui():
            progress = gr.Progress()
            julia_path = install_julia(progress)
            if julia_path:
                return f"Julia installed successfully at: {julia_path}"
            else:
                return "Failed to install Julia"
        
        def setup_julia_ui():
            progress = gr.Progress()
            julia_path = check_julia_installation()
            if not julia_path:
                return "Julia is not installed or not found in PATH"
            
            if setup_julia_packages(julia_path, progress):
                return "Julia packages set up successfully"
            else:
                return "Failed to set up Julia packages"
        
        # Set initial status
        status_output.value = check_julia()
        
        # Connect buttons
        install_button.click(install_julia_ui, outputs=status_output)
        setup_button.click(setup_julia_ui, outputs=status_output)
    
    return app

if __name__ == "__main__":
    julia_installation_ui().launch() 