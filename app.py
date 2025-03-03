import os
import tempfile
import shutil
import zipfile
import subprocess
import sys
import platform
import importlib

# Global variable to track if FFmpeg was found by run.bat
FFMPEG_FOUND = False

# Check if FFmpeg was added to PATH by run.bat
if os.environ.get('FFMPEG_ADDED_TO_PATH') == 'true':
    FFMPEG_FOUND = True
    print("FFmpeg was added to PATH by run.bat")

# Function to check if a package is installed
def is_package_installed(package_name):
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False

# Function to install missing packages
def install_missing_packages():
    """Install missing Python packages."""
    try:
        print("Installing missing packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ All required packages installed successfully")
        return True
    except Exception as e:
        print(f"❌ Error installing packages: {str(e)}")
        return False

# Check if we need to install packages
if not os.environ.get('BEATSABER_APP_STARTED') == '1':
    os.environ['BEATSABER_APP_STARTED'] = '1'
    if install_missing_packages():
        print("Restarting application to load newly installed packages...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

# Now import the modules (after ensuring they're installed)
try:
    import gradio as gr
    import uuid
    import time
    from generate_cover import generate_cover_image
    from julia_setup import check_julia_installation, ensure_julia_installation, setup_julia_packages, setup_pyjulia
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please make sure all required packages are installed.")
    sys.exit(1)

# Configuration
TEMP_DIR = "temp_uploads"
OUTPUT_DIR = "output_maps"
JULIA_PATH = None  # Will be set dynamically

# Create directories if they don't exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def check_command(command, name):
    """Check if a command is available."""
    # For FFmpeg, first check if it's in the PATH
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

def check_and_setup_environment():
    """Check and setup the environment."""
    global JULIA_PATH
    
    print("Checking and setting up environment...")
    
    # Check Julia
    julia_path = check_julia_installation()
    if julia_path:
        print(f"✅ Julia is installed at: {julia_path}")
        JULIA_PATH = julia_path
    else:
        print("❌ Julia is not installed. It will be installed when needed.")
    
    return True

def process_audio_file(audio_file, difficulties_arg, progress=gr.Progress()):
    """Process an audio file and generate Beat Saber maps"""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {str(e)}")
            print(description)
    
    if audio_file is None:
        return None
    
    # Ensure Julia is installed
    global JULIA_PATH
    if not JULIA_PATH:
        update_progress(0.1, "Julia not found. Installing Julia...")
        JULIA_PATH = ensure_julia_installation(progress)
        if not JULIA_PATH:
            return gr.update(value="Error: Failed to install Julia", visible=True)
    
    # Generate a unique ID for this job
    job_id = str(uuid.uuid4())
    output_folder = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_folder, exist_ok=True)
    
    # Create a log file for this job
    log_file = os.path.join(output_folder, "process_log.txt")
    
    # Function to log messages both to console and log file
    def log_message(message):
        print(message)
        with open(log_file, "a") as f:
            f.write(message + "\n")
    
    log_message(f"Starting job {job_id}")
    
    # Handle both string paths and file objects
    if isinstance(audio_file, str):
        file_path = audio_file
        file_name = os.path.basename(file_path)
    else:
        # It's a file object with a name attribute
        file_path = audio_file.name
        file_name = os.path.basename(file_path)
    
    song_name = os.path.splitext(file_name)[0]
    log_message(f"Processing song: {song_name}")
    
    # Copy the file to our temp directory
    temp_file_path = os.path.join(TEMP_DIR, file_name)
    shutil.copy(file_path, temp_file_path)
    
    update_progress(0.1, "Audio file uploaded")
    log_message("Audio file uploaded to temp directory")
    
    try:
        # Run the Julia script to process the audio file
        update_progress(0.2, "Starting Beat Saber map generation")
        
        # Create a temporary file to store the difficulties
        difficulties_file = os.path.join(TEMP_DIR, f"{job_id}_difficulties.txt")
        with open(difficulties_file, "w") as f:
            f.write(difficulties_arg)
        
        # Get the ffmpeg path
        ffmpeg_path = None
        if FFMPEG_FOUND:
            ffmpeg_path = "ffmpeg"  # It's in the PATH
        else:
            # Check if ffmpeg is in the ffmpeg directory (directly, not in bin)
            ffmpeg_dir = os.path.join(os.getcwd(), "ffmpeg")
            if os.path.exists(ffmpeg_dir):
                # First check if ffmpeg.exe is directly in the ffmpeg folder
                ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
                if os.path.exists(ffmpeg_exe):
                    ffmpeg_path = ffmpeg_exe
                    print(f"Found FFmpeg at: {ffmpeg_path}")
                # Also check bin subfolder as fallback
                elif os.path.exists(os.path.join(ffmpeg_dir, "bin")):
                    ffmpeg_exe = os.path.join(ffmpeg_dir, "bin", "ffmpeg.exe")
                    if os.path.exists(ffmpeg_exe):
                        ffmpeg_path = ffmpeg_exe
                        print(f"Found FFmpeg at: {ffmpeg_path}")
        
        if not ffmpeg_path:
            return "Error: ffmpeg not found. Please install ffmpeg."
        
        # Create a config file to pass additional parameters
        config_file = os.path.join(TEMP_DIR, f"{job_id}_config.txt")
        with open(config_file, "w") as f:
            f.write(f"ffmpeg_path={ffmpeg_path}\n")
        
        # Pass the difficulties file path and config file path
        cmd = [JULIA_PATH, "src/mapsongs.jl", temp_file_path, difficulties_file, config_file]
        log_message(f"Executing command: {' '.join(cmd)}")
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace')
            log_message(f"Error: Process returned non-zero exit code {process.returncode}")
            
            # Log the error details to the log file
            log_message("===== ERROR DETAILS =====")
            log_message(f"Error message: {error_msg[:1000]}..." if len(error_msg) > 1000 else f"Error message: {error_msg}")
            log_message("===== STDOUT =====")
            stdout_content = stdout.decode('utf-8', errors='replace')
            log_message(stdout_content[:1000] + "..." if len(stdout_content) > 1000 else stdout_content)
            
            # Add helpful suggestions based on the error
            log_message("===== TROUBLESHOOTING =====")
            if "no such file or directory" in error_msg and "ffmpeg" in error_msg:
                log_message("Possible FFmpeg issue detected:")
                log_message(f"Current FFmpeg path: {ffmpeg_path}")
                
                # Check for FFmpeg in common locations
                log_message("Checking for FFmpeg in common locations:")
                possible_paths = [
                    os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe"),
                    os.path.join(os.getcwd(), "ffmpeg", "bin", "ffmpeg.exe")
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        log_message(f"Found FFmpeg at: {path}")
            elif "adelay" in error_msg:
                log_message("Possible issue with FFmpeg adelay filter")
            elif "WAV" in error_msg and "not found" in error_msg:
                log_message("Julia WAV package may be missing")
            
            # Return a simple error message to avoid HTTP issues
            return gr.update(
                value=f"Error processing file. See log file for details: {os.path.basename(log_file)}",
                visible=True
            )
        
        update_progress(0.7, "Maps generated, preparing download")
        
        # Find the generated folder (it has a random prefix)
        generated_folders = [f for f in os.listdir() if f.endswith("_" + song_name) and os.path.isdir(f)]
        if not generated_folders:
            log_message("Error: Could not find generated map folder")
            log_message(f"Looking for folders ending with: _{song_name}")
            log_message(f"Current directory: {os.getcwd()}")
            log_message(f"Files in current directory: {', '.join(os.listdir()[:20])}")  # Limit to first 20 files
            
            return gr.update(
                value=f"Error: Could not find generated map folder. See log file for details: {os.path.basename(log_file)}",
                visible=True
            )
        
        generated_folder = generated_folders[0]
        
        # Generate a cover image if one doesn't exist
        cover_path = os.path.join(generated_folder, "cover.jpg")
        if not os.path.exists(cover_path):
            update_progress(0.8, "Generating cover image")
            generate_cover_image(cover_path, song_name)
        
        # Create a zip file of the generated maps
        update_progress(0.9, "Creating zip file")
        zip_path = os.path.join(output_folder, f"{song_name}_beatsaber_maps.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(generated_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.join(os.path.basename(root), file))
        
        # Clean up the generated folder
        shutil.rmtree(generated_folder)
        
        update_progress(1.0, "Done!")
        return zip_path
    
    except Exception as e:
        error_message = str(e)
        log_message(f"Unexpected error: {error_message}")
        log_message(f"Exception type: {type(e).__name__}")
        
        # Log the traceback
        import traceback
        tb = traceback.format_exc()
        log_message("===== TRACEBACK =====")
        log_message(tb)
        
        return gr.update(
            value=f"Error processing file. See log file for details: {os.path.basename(log_file)}",
            visible=True
        )
    finally:
        # Clean up the temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def install_julia_handler(progress=gr.Progress()):
    """Handler for installing Julia from the UI."""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {str(e)}")
            print(description)
    
    try:
        update_progress(0.1, "Starting Julia installation...")
        julia_path = ensure_julia_installation(progress)
        
        if julia_path:
            global JULIA_PATH
            JULIA_PATH = julia_path
            return f"Julia installed successfully at: {julia_path}"
        else:
            return "Failed to install Julia. Please check the console for more information."
    except Exception as e:
        print(f"Error during Julia installation: {str(e)}")
        return f"Error during Julia installation: {str(e)}"

def setup_julia_packages_handler(progress=gr.Progress()):
    """Handler for setting up Julia packages from the UI."""
    # Helper function to safely update progress
    def update_progress(value, description):
        try:
            if progress:
                progress(value, description)
        except Exception as e:
            print(f"Progress update error (non-critical): {str(e)}")
            print(description)
    
    try:
        update_progress(0.1, "Starting Julia package setup...")
        success = setup_julia_packages(progress)
        
        if success:
            return "Julia packages set up successfully!"
        else:
            return "Failed to set up Julia packages. Please check the console for more information."
    except Exception as e:
        print(f"Error during Julia package setup: {str(e)}")
        return f"Error during Julia package setup: {str(e)}"

# Run the environment check and setup
check_and_setup_environment()

# Create a custom Beat Saber theme
beat_saber_colors = {
    "primary_hue": "blue",
    "secondary_hue": "red",
    "neutral_hue": "gray",  # Changed from slate to gray for darker tones
    "spacing_size": gr.themes.sizes.spacing_md,
    "radius_size": gr.themes.sizes.radius_md,
    "text_size": gr.themes.sizes.text_md,
    "font": gr.themes.GoogleFont("Exo 2"),  # Beat Saber uses a similar font
    "font_mono": gr.themes.GoogleFont("Roboto Mono")
}

beat_saber_theme = gr.themes.Soft(
    primary_hue=beat_saber_colors["primary_hue"],
    secondary_hue=beat_saber_colors["secondary_hue"],
    neutral_hue=beat_saber_colors["neutral_hue"],
    spacing_size=beat_saber_colors["spacing_size"],
    radius_size=beat_saber_colors["radius_size"],
    text_size=beat_saber_colors["text_size"],
    font=beat_saber_colors["font"],
    font_mono=beat_saber_colors["font_mono"]
)

# Custom CSS for Beat Saber styling
beat_saber_css = """
:root {
    --bs-blue: #0078ff;
    --bs-light-blue: #00aaff;
    --bs-red: #ff3355;
    --bs-background: #090a1a;
    --bs-accent: #1a1b2e;
    --bs-text: #ffffff;
    --bs-glow-blue: 0 0 10px rgba(0, 170, 255, 0.7);
    --bs-glow-red: 0 0 10px rgba(255, 51, 85, 0.7);
}

body, .gradio-container {
    background-color: var(--bs-background) !important;
    color: var(--bs-text) !important;
    background-image: 
        radial-gradient(circle at 20% 30%, rgba(0, 120, 255, 0.1) 0%, transparent 40%),
        radial-gradient(circle at 80% 70%, rgba(255, 51, 85, 0.1) 0%, transparent 40%);
}

.main-header {
    text-align: center;
    margin-bottom: 1.5rem;
    text-transform: uppercase;
    letter-spacing: 3px;
    background: linear-gradient(90deg, var(--bs-light-blue), var(--bs-red));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    font-size: 3rem;
    padding: 20px;
    text-shadow: var(--bs-glow-blue), var(--bs-glow-red);
    position: relative;
}

.main-header::before, .main-header::after {
    content: '';
    position: absolute;
    width: 120px;
    height: 3px;
    background: linear-gradient(90deg, var(--bs-light-blue), var(--bs-red));
    left: 50%;
    transform: translateX(-50%);
}

.main-header::before {
    top: 5px;
}

.main-header::after {
    bottom: 5px;
}

.subtitle {
    text-align: center;
    margin-bottom: 2rem;
    font-size: 1.2rem;
    color: #cccccc !important;
    font-weight: 300;
    letter-spacing: 1px;
}

.tab-nav {
    background-color: transparent !important;
    border: none !important;
}

.tab-nav button {
    background: var(--bs-accent) !important;
    color: var(--bs-text) !important;
    border: none !important;
    border-radius: 5px !important;
    margin: 0 5px !important;
    padding: 10px 20px !important;
    transition: all 0.3s ease !important;
    position: relative;
    overflow: hidden;
    z-index: 1;
}

.tab-nav button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, var(--bs-light-blue), var(--bs-red), transparent);
    transition: all 0.4s ease;
    z-index: -1;
    opacity: 0.7;
}

.tab-nav button:hover::before {
    left: 0;
}

.tab-nav button.selected {
    background: var(--bs-accent) !important;
    transform: translateY(-3px) !important;
    box-shadow: var(--bs-glow-blue), var(--bs-glow-red) !important;
    color: white !important;
    font-weight: bold !important;
}

.tab-nav button.selected::before {
    left: 0;
}

button.primary {
    background: linear-gradient(90deg, var(--bs-blue), var(--bs-red)) !important;
    border: none !important;
    color: white !important;
    font-weight: bold !important;
    transition: all 0.3s ease !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    position: relative;
    overflow: hidden;
    z-index: 1;
}

button.primary::after {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: linear-gradient(45deg, transparent, rgba(255,255,255,0.2), transparent);
    transform: rotate(45deg);
    transition: all 0.6s ease;
    z-index: -1;
}

button.primary:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3) !important;
}

button.primary:hover::after {
    left: 100%;
}

.difficulty-checkbox label {
    font-weight: bold !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
}

.difficulty-checkbox:hover {
    transform: translateY(-2px);
}

.easy-label span {
    color: #3CB371 !important;
    text-shadow: 0 0 5px rgba(60, 179, 113, 0.5) !important;
}

.normal-label span {
    color: #1E90FF !important;
    text-shadow: 0 0 5px rgba(30, 144, 255, 0.5) !important;
}

.hard-label span {
    color: #FFD700 !important;
    text-shadow: 0 0 5px rgba(255, 215, 0, 0.5) !important;
}

.expert-label span {
    color: #FF4500 !important;
    text-shadow: 0 0 5px rgba(255, 69, 0, 0.5) !important;
}

.expert-plus-label span {
    color: #9370DB !important;
    text-shadow: 0 0 5px rgba(147, 112, 219, 0.5) !important;
}

.panel {
    border-radius: 10px !important;
    background-color: var(--bs-accent) !important;
    padding: 20px !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3) !important;
    margin-bottom: 20px !important;
    border: 1px solid rgba(0, 170, 255, 0.2) !important;
    position: relative;
    overflow: hidden;
}

.panel::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 2px;
    background: linear-gradient(90deg, var(--bs-light-blue), var(--bs-red));
}

.status-message {
    border-radius: 5px !important;
    padding: 10px !important;
    margin-top: 10px !important;
    font-weight: bold !important;
}

.status-success {
    background-color: rgba(76, 175, 80, 0.2) !important;
    color: #4CAF50 !important;
    border-left: 3px solid #4CAF50 !important;
}

.status-warning {
    background-color: rgba(255, 152, 0, 0.2) !important;
    color: #FF9800 !important;
    border-left: 3px solid #FF9800 !important;
}

.status-error {
    background-color: rgba(244, 67, 54, 0.2) !important;
    color: #F44336 !important;
    border-left: 3px solid #F44336 !important;
}

/* Custom file upload */
.file-upload {
    border: 2px dashed var(--bs-blue) !important;
    border-radius: 10px !important;
    padding: 20px !important;
    text-align: center !important;
    transition: all 0.3s ease !important;
    background-color: rgba(0, 120, 255, 0.05) !important;
}

.file-upload:hover {
    border-color: var(--bs-red) !important;
    background-color: rgba(255, 51, 85, 0.05) !important;
    box-shadow: var(--bs-glow-blue), var(--bs-glow-red) !important;
}

/* Custom loader animation */
@keyframes beat {
    0%, 100% { transform: scale(1); opacity: 0.8; }
    50% { transform: scale(1.2); opacity: 1; }
}

.loader-container {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    margin: 20px 0 !important;
}

.beat-loader {
    width: 20px !important;
    height: 20px !important;
    border-radius: 50% !important;
    margin: 0 5px !important;
    animation: beat 1s infinite !important;
    box-shadow: 0 0 10px currentColor !important;
}

.beat-loader:nth-child(1) {
    background-color: var(--bs-light-blue) !important;
    animation-delay: 0s !important;
}

.beat-loader:nth-child(2) {
    background-color: var(--bs-red) !important;
    animation-delay: 0.2s !important;
}

.beat-loader:nth-child(3) {
    background-color: var(--bs-light-blue) !important;
    animation-delay: 0.4s !important;
}

.beat-loader:nth-child(4) {
    background-color: var(--bs-red) !important;
    animation-delay: 0.6s !important;
}

/* Beat Saber cube styling */
.beat-cube {
    position: relative;
    width: 50px;
    height: 50px;
    margin: 15px auto;
    transform-style: preserve-3d;
    animation: rotate 10s infinite linear;
}

@keyframes rotate {
    0% { transform: rotateX(-20deg) rotateY(0deg); }
    100% { transform: rotateX(-20deg) rotateY(360deg); }
}

.cube-face {
    position: absolute;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 170, 255, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.5);
    box-shadow: 0 0 10px rgba(0, 170, 255, 0.5);
}

.face-front { transform: translateZ(25px); }
.face-back { transform: translateZ(-25px) rotateY(180deg); }
.face-left { transform: translateX(-25px) rotateY(-90deg); }
.face-right { transform: translateX(25px) rotateY(90deg); }
.face-top { transform: translateY(-25px) rotateX(90deg); }
.face-bottom { transform: translateY(25px) rotateX(-90deg); }

.face-front::after, .face-back::after, .face-left::after, .face-right::after, .face-top::after, .face-bottom::after {
    content: '';
    position: absolute;
    width: 80%;
    height: 80%;
    top: 10%;
    left: 10%;
    background-color: rgba(255, 255, 255, 0.1);
}

/* Red cube for variation */
.beat-cube-red .cube-face {
    background-color: rgba(255, 51, 85, 0.7);
    box-shadow: 0 0 10px rgba(255, 51, 85, 0.5);
}

/* Sword slash effect */
.slash {
    position: absolute;
    width: 100%;
    height: 5px;
    background: linear-gradient(90deg, transparent, white, transparent);
    animation: slash 2s infinite ease-out;
    opacity: 0;
}

@keyframes slash {
    0% { transform: translateY(25px) rotate(-45deg); opacity: 0; width: 0; }
    10% { opacity: 0.9; }
    50% { width: 150%; }
    100% { transform: translateY(-25px) rotate(-45deg); opacity: 0; width: 150%; }
}

/* Background grid effect */
.bs-grid {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-image: 
        linear-gradient(to right, rgba(30, 144, 255, 0.05) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(30, 144, 255, 0.05) 1px, transparent 1px);
    background-size: 30px 30px;
    z-index: -1;
}

input, select, textarea {
    background-color: rgba(0, 0, 0, 0.3) !important;
    border: 1px solid rgba(0, 170, 255, 0.3) !important;
    color: white !important;
}

input:focus, select:focus, textarea:focus {
    border-color: var(--bs-light-blue) !important;
    box-shadow: var(--bs-glow-blue) !important;
}

/* Card hover effects */
.panel:hover {
    transform: translateY(-3px);
    transition: transform 0.3s ease;
}
"""

# Create the Gradio interface with custom theme
with gr.Blocks(title="Beat Saber Automatic Mapper", theme=beat_saber_theme, css=beat_saber_css) as app:
    # Check if Julia is installed
    if not JULIA_PATH:
        JULIA_PATH = check_julia_installation()
    
    # Check if ffmpeg is installed
    ffmpeg_installed = check_command("ffmpeg", "ffmpeg") or FFMPEG_FOUND
    
    # Background grid effect
    gr.HTML('<div class="bs-grid"></div>')
    
    gr.HTML("""
    <h1 class="main-header">Beat Saber Automatic Mapper</h1>
    <p class="subtitle">Transform your music into epic Beat Saber levels with AI-powered mapping</p>
    """)
    
    with gr.Tabs() as tabs:
        with gr.TabItem("🎵 Create Maps"):
            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Group(elem_classes=["panel"]):
                        gr.HTML("""
                        <h3 style="margin-top:0; text-align:center; color: #00aaff; text-shadow: 0 0 5px rgba(0, 170, 255, 0.5);">
                            Upload Your Music
                        </h3>
                        
                        <!-- Beat Saber cube -->
                        <div class="beat-cube">
                            <div class="cube-face face-front"></div>
                            <div class="cube-face face-back"></div>
                            <div class="cube-face face-left"></div>
                            <div class="cube-face face-right"></div>
                            <div class="cube-face face-top"></div>
                            <div class="cube-face face-bottom"></div>
                            <div class="slash"></div>
                        </div>
                        """)
                        audio_input = gr.Audio(
                            type="filepath", 
                            label="", 
                            elem_classes=["file-upload"]
                        )
                        
                        # Add difficulty selection options with custom styling
                        gr.HTML("""<h3 style="margin-top:20px; text-align:center; color: #ff3355; text-shadow: 0 0 5px rgba(255, 51, 85, 0.5);">Select Difficulty Levels</h3>""")
                        with gr.Row():
                            easy_checkbox = gr.Checkbox(value=True, label="Easy", elem_classes=["difficulty-checkbox", "easy-label"])
                            normal_checkbox = gr.Checkbox(value=True, label="Normal", elem_classes=["difficulty-checkbox", "normal-label"])
                        with gr.Row():
                            hard_checkbox = gr.Checkbox(value=True, label="Hard", elem_classes=["difficulty-checkbox", "hard-label"])
                            expert_checkbox = gr.Checkbox(value=True, label="Expert", elem_classes=["difficulty-checkbox", "expert-label"])
                        with gr.Row():
                            expert_plus_checkbox = gr.Checkbox(value=True, label="Expert+", elem_classes=["difficulty-checkbox", "expert-plus-label"])
                        
                        audio_submit = gr.Button("Generate Beat Saber Maps", elem_classes=["primary"])
                        
                        # Custom loading animation (visible when processing)
                        gr.HTML("""
                        <div class="loader-container">
                            <div class="beat-loader"></div>
                            <div class="beat-loader"></div>
                            <div class="beat-loader"></div>
                            <div class="beat-loader"></div>
                        </div>
                        """)
                        
                        # Status message with conditional styling
                        audio_status_class = "status-message " + (
                            "status-warning" if not ffmpeg_installed else "status-success"
                        )
                        audio_status = gr.Markdown(
                            "Upload an audio file and click 'Generate Maps'" if ffmpeg_installed else 
                            "⚠️ ffmpeg is not installed. Please install it to process audio files.",
                            elem_classes=[audio_status_class]
                        )
                
                with gr.Column(scale=1):
                    with gr.Group(elem_classes=["panel"]):
                        gr.HTML("""
                        <h3 style="margin-top:0; text-align:center; color: #00aaff; text-shadow: 0 0 5px rgba(0, 170, 255, 0.5);">
                            Your Beat Saber Maps
                        </h3>
                        
                        <!-- Red Beat Saber cube -->
                        <div class="beat-cube beat-cube-red">
                            <div class="cube-face face-front"></div>
                            <div class="cube-face face-back"></div>
                            <div class="cube-face face-left"></div>
                            <div class="cube-face face-right"></div>
                            <div class="cube-face face-top"></div>
                            <div class="cube-face face-bottom"></div>
                            <div class="slash"></div>
                        </div>
                        
                        <div style="text-align:center; margin-bottom:20px;">
                            
                        </div>
                        """)
                        audio_output = gr.File(label="Download Your Maps")
                        gr.HTML("""
                        <div style="margin-top:20px; text-align:center;">
                            <p style="color: #cccccc; font-weight: 300; letter-spacing: 0.5px;">Your Beat Saber map will include:</p>
                            <ul style="text-align:left; color: #cccccc; font-weight: 300;">
                                <li style="margin-bottom: 8px;"><span style="color: #00aaff; font-weight: bold;">✓</span> Custom beat mapping for each difficulty level</li>
                                <li style="margin-bottom: 8px;"><span style="color: #00aaff; font-weight: bold;">✓</span> Automatically generated cover image</li>
                                <li style="margin-bottom: 8px;"><span style="color: #00aaff; font-weight: bold;">✓</span> Ready-to-play map files</li>
                            </ul>
                        </div>
                        """)
        
        with gr.TabItem("⚙️ Setup"):
            with gr.Row():
                with gr.Column():
                    with gr.Group(elem_classes=["panel"]):
                        gr.HTML("""
                        <h3 style="margin-top:0; text-align:center; color: #00aaff; text-shadow: 0 0 5px rgba(0, 170, 255, 0.5);">
                            Julia Setup
                        </h3>
                        
                        <!-- Beat Saber cube -->
                        <div class="beat-cube">
                            <div class="cube-face face-front"></div>
                            <div class="cube-face face-back"></div>
                            <div class="cube-face face-left"></div>
                            <div class="cube-face face-right"></div>
                            <div class="cube-face face-top"></div>
                            <div class="cube-face face-bottom"></div>
                        </div>
                        """)
                        
                        # Status with conditional styling
                        julia_status_class = "status-message " + (
                            "status-success" if JULIA_PATH else "status-error"
                        )
                        julia_status = gr.Markdown(
                            f"✅ Julia is installed at: {JULIA_PATH}" if JULIA_PATH else 
                            "❌ Julia is not installed. Click the button below to install it.",
                            elem_classes=[julia_status_class]
                        )
                        
                        with gr.Row():
                            install_julia_button = gr.Button(
                                "Install Julia" if not JULIA_PATH else "Reinstall Julia", 
                                elem_classes=["primary"]
                            )
                            setup_packages_button = gr.Button(
                                "Setup Julia Packages", 
                                elem_classes=["primary"]
                            )
                        
                        setup_status = gr.Markdown("", elem_classes=["status-message"])
                
                with gr.Column():
                    with gr.Group(elem_classes=["panel"]):
                        gr.HTML("""
                        <h3 style="margin-top:0; text-align:center; color: #ff3355; text-shadow: 0 0 5px rgba(255, 51, 85, 0.5);">
                            Environment Status
                        </h3>
                        
                        <!-- Red Beat Saber cube -->
                        <div class="beat-cube beat-cube-red">
                            <div class="cube-face face-front"></div>
                            <div class="cube-face face-back"></div>
                            <div class="cube-face face-left"></div>
                            <div class="cube-face face-right"></div>
                            <div class="cube-face face-top"></div>
                            <div class="cube-face face-bottom"></div>
                        </div>
                        """)
                        
                        env_status = gr.HTML(f"""
                        <div style="text-align:center;">
                            <div style="margin: 10px 0; padding: 15px; border-radius: 8px; 
                                 background-color: {JULIA_PATH and 'rgba(0, 170, 255, 0.1)' or 'rgba(255, 51, 85, 0.1)'};
                                 color: {JULIA_PATH and '#00aaff' or '#ff3355'};
                                 border-left: 3px solid {JULIA_PATH and '#00aaff' or '#ff3355'};
                                 transition: all 0.3s ease;">
                                <span style="font-size: 24px;">{JULIA_PATH and '✅' or '❌'}</span>
                                <strong>Julia:</strong> {JULIA_PATH and 'Installed' or 'Not installed'}
                            </div>
                            
                            <div style="margin: 10px 0; padding: 15px; border-radius: 8px;
                                 background-color: {ffmpeg_installed and 'rgba(0, 170, 255, 0.1)' or 'rgba(255, 51, 85, 0.1)'};
                                 color: {ffmpeg_installed and '#00aaff' or '#ff3355'};
                                 border-left: 3px solid {ffmpeg_installed and '#00aaff' or '#ff3355'};
                                 transition: all 0.3s ease;">
                                <span style="font-size: 24px;">{ffmpeg_installed and '✅' or '❌'}</span>
                                <strong>FFmpeg:</strong> {ffmpeg_installed and 'Installed' or 'Not installed'}
                            </div>
                        </div>
                        """)
        
        with gr.TabItem("ℹ️ Help"):
            with gr.Group(elem_classes=["panel"]):
                gr.HTML("""
                <h3 style="margin-top:0; text-align:center; color: #00aaff; text-shadow: 0 0 5px rgba(0, 170, 255, 0.5);">
                    Troubleshooting
                </h3>
                
                <div style="display: flex; justify-content: center; margin: 20px 0;">
                    <div class="beat-cube">
                        <div class="cube-face face-front"></div>
                        <div class="cube-face face-back"></div>
                        <div class="cube-face face-left"></div>
                        <div class="cube-face face-right"></div>
                        <div class="cube-face face-top"></div>
                        <div class="cube-face face-bottom"></div>
                    </div>
                    
                    <div class="beat-cube beat-cube-red" style="margin-left: 30px;">
                        <div class="cube-face face-front"></div>
                        <div class="cube-face face-back"></div>
                        <div class="cube-face face-left"></div>
                        <div class="cube-face face-right"></div>
                        <div class="cube-face face-top"></div>
                        <div class="cube-face face-bottom"></div>
                    </div>
                </div>
                
                <div style="background-color: rgba(0, 170, 255, 0.05); padding: 20px; border-radius: 8px; margin-bottom: 20px; 
                         border-left: 3px solid #00aaff; transition: all 0.3s ease;">
                    <h4 style="margin-top:0; color: #00aaff; text-shadow: 0 0 3px rgba(0, 170, 255, 0.3);">Julia Installation Issues</h4>
                    <p style="color: #cccccc; font-weight: 300;">If Julia installation fails through the app:</p>
                    <ol style="color: #cccccc; font-weight: 300;">
                        <li style="margin-bottom: 8px;">Download Julia manually from <a href="https://julialang.org/downloads/" target="_blank" style="color: #00aaff; text-decoration: none; border-bottom: 1px dotted #00aaff;">julialang.org/downloads</a></li>
                        <li style="margin-bottom: 8px;">Install Julia and make sure it's in your system PATH</li>
                        <li style="margin-bottom: 8px;">Restart this application</li>
                    </ol>
                </div>
                
                <div style="background-color: rgba(255, 51, 85, 0.05); padding: 20px; border-radius: 8px; margin-bottom: 20px;
                         border-left: 3px solid #ff3355; transition: all 0.3s ease;">
                    <h4 style="margin-top:0; color: #ff3355; text-shadow: 0 0 3px rgba(255, 51, 85, 0.3);">Audio Processing Issues</h4>
                    <p style="color: #cccccc; font-weight: 300;">If audio file processing fails:</p>
                    <ul style="color: #cccccc; font-weight: 300;">
                        <li style="margin-bottom: 8px;">Make sure FFmpeg is installed and in your system PATH</li>
                        <li style="margin-bottom: 8px;">Check that your audio file is a valid format (MP3, WAV, FLAC, etc.)</li>
                        <li style="margin-bottom: 8px;">Try a different audio file</li>
                    </ul>
                </div>
                
                <h3 style="text-align:center; color: #00aaff; text-shadow: 0 0 5px rgba(0, 170, 255, 0.5); margin-top: 40px;">
                    How It Works
                </h3>
                
                <div style="display: flex; justify-content: space-between; flex-wrap: wrap; margin-top: 30px;">
                    <div style="flex: 1; min-width: 250px; background-color: rgba(0, 170, 255, 0.05); padding: 20px; border-radius: 8px; margin: 10px;
                             border-top: 2px solid #00aaff; transition: all 0.3s ease;"
                             onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 0 15px rgba(0, 170, 255, 0.3)';"
                             onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none';">
                        <h4 style="margin-top:0; color: #00aaff; text-shadow: 0 0 3px rgba(0, 170, 255, 0.3); text-align: center;">
                            1. Analysis
                        </h4>
                        <div style="width: 40px; height: 3px; background: linear-gradient(90deg, #00aaff, transparent); margin: 10px auto 15px;"></div>
                        <p style="color: #cccccc; font-weight: 300;">The app analyzes your audio file to detect beats, rhythm patterns, and energy levels.</p>
                    </div>
                    
                    <div style="flex: 1; min-width: 250px; background-color: rgba(255, 51, 85, 0.05); padding: 20px; border-radius: 8px; margin: 10px;
                             border-top: 2px solid #ff3355; transition: all 0.3s ease;"
                             onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 0 15px rgba(255, 51, 85, 0.3)';" 
                             onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none';">
                        <h4 style="margin-top:0; color: #ff3355; text-shadow: 0 0 3px rgba(255, 51, 85, 0.3); text-align: center;">
                            2. Generation
                        </h4>
                        <div style="width: 40px; height: 3px; background: linear-gradient(90deg, #ff3355, transparent); margin: 10px auto 15px;"></div>
                        <p style="color: #cccccc; font-weight: 300;">Based on the analysis, custom beat maps are created for each selected difficulty level.</p>
                    </div>
                    
                    <div style="flex: 1; min-width: 250px; background-color: rgba(0, 170, 255, 0.05); padding: 20px; border-radius: 8px; margin: 10px;
                             border-top: 2px solid #00aaff; transition: all 0.3s ease;"
                             onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 0 15px rgba(0, 170, 255, 0.3)';"
                             onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none';">
                        <h4 style="margin-top:0; color: #00aaff; text-shadow: 0 0 3px rgba(0, 170, 255, 0.3); text-align: center;">
                            3. Packaging
                        </h4>
                        <div style="width: 40px; height: 3px; background: linear-gradient(90deg, #00aaff, transparent); margin: 10px auto 15px;"></div>
                        <p style="color: #cccccc; font-weight: 300;">The app packages all the maps with a custom cover image into a ready-to-use Beat Saber level.</p>
                    </div>
                </div>
                """)
    
    def update_audio_status(audio_file):
        if not audio_file:
            return "Please upload an audio file"
        if not (check_command("ffmpeg", "ffmpeg") or FFMPEG_FOUND):
            return "ffmpeg is not installed. Please install it to process audio files."
        return "Processing audio file. This may take a few minutes..."
    
    # Process audio with difficulty options
    def process_audio_with_difficulties(audio_file, easy, normal, hard, expert, expert_plus, progress=gr.Progress()):
        # Create a list of selected difficulties
        difficulties = []
        if easy:
            difficulties.append("Easy")
        if normal:
            difficulties.append("Normal")
        if hard:
            difficulties.append("Hard")
        if expert:
            difficulties.append("Expert")
        if expert_plus:
            difficulties.append("ExpertPlus")
        
        # If no difficulties selected, default to all
        if not difficulties:
            difficulties = ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"]
        
        # Convert difficulties to command-line argument - one per line for easier parsing in Julia
        difficulties_arg = "\n".join(difficulties)
        
        # Call the original process_audio_file function with the difficulties
        return process_audio_file(audio_file, difficulties_arg, progress)
    
    # Setup event handlers
    install_julia_button.click(
        install_julia_handler,
        outputs=[setup_status]
    ).then(
        lambda: f"✅ Julia is installed at: {check_julia_installation()}" if check_julia_installation() else "❌ Julia installation failed",
        outputs=[julia_status]
    )
    
    setup_packages_button.click(
        setup_julia_packages_handler,
        outputs=[setup_status]
    )
    
    audio_submit.click(
        update_audio_status,
        inputs=[audio_input],
        outputs=[audio_status]
    ).then(
        process_audio_with_difficulties,
        inputs=[audio_input, easy_checkbox, normal_checkbox, hard_checkbox, expert_checkbox, expert_plus_checkbox],
        outputs=[audio_output]
    ).then(
        lambda: "Processing complete! Download your maps above.",
        outputs=[audio_status]
    )

if __name__ == "__main__":
    app.launch() 
