#!/usr/bin/env python
"""
Script to download and start GeoServer for the Property Mapper application.
This script handles the following tasks:
1. Checks if GeoServer is already installed
2. Downloads GeoServer if needed
3. Sets up the GeoServer data directory
4. Starts GeoServer with the appropriate configuration
"""
import os
import sys
import subprocess
import zipfile
import shutil
import requests
import time
import signal
from pathlib import Path

# Configuration
GEOSERVER_VERSION = "2.23.2"  # Latest stable version as of March 2025
GEOSERVER_BASE_DIR = "geoserver"
GEOSERVER_DATA_DIR = os.path.join(GEOSERVER_BASE_DIR, "data_dir")
GEOSERVER_DOWNLOAD_URL = f"https://sourceforge.net/projects/geoserver/files/GeoServer/{GEOSERVER_VERSION}/geoserver-{GEOSERVER_VERSION}-bin.zip"

# Create the base directory if it doesn't exist
os.makedirs(GEOSERVER_BASE_DIR, exist_ok=True)

def check_geoserver_installed():
    """Check if GeoServer is already installed."""
    geoserver_dir = os.path.join(GEOSERVER_BASE_DIR, f"geoserver-{GEOSERVER_VERSION}")
    return os.path.exists(geoserver_dir)

def download_geoserver():
    """Download GeoServer if not already downloaded."""
    geoserver_zip = os.path.join(GEOSERVER_BASE_DIR, f"geoserver-{GEOSERVER_VERSION}.zip")
    
    if not os.path.exists(geoserver_zip):
        print(f"Downloading GeoServer {GEOSERVER_VERSION}...")
        try:
            response = requests.get(GEOSERVER_DOWNLOAD_URL, stream=True)
            response.raise_for_status()
            
            with open(geoserver_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Download complete.")
        except Exception as e:
            print(f"Error downloading GeoServer: {e}")
            sys.exit(1)
    else:
        print(f"GeoServer ZIP already downloaded.")
    
    # Extract the ZIP file
    geoserver_dir = os.path.join(GEOSERVER_BASE_DIR, f"geoserver-{GEOSERVER_VERSION}")
    if not os.path.exists(geoserver_dir):
        print("Extracting GeoServer...")
        try:
            with zipfile.ZipFile(geoserver_zip, 'r') as zip_ref:
                zip_ref.extractall(GEOSERVER_BASE_DIR)
            print("Extraction complete.")
        except Exception as e:
            print(f"Error extracting GeoServer: {e}")
            sys.exit(1)
    else:
        print("GeoServer already extracted.")

def setup_data_directory():
    """Set up the GeoServer data directory."""
    if not os.path.exists(GEOSERVER_DATA_DIR):
        print("Setting up GeoServer data directory...")
        os.makedirs(GEOSERVER_DATA_DIR, exist_ok=True)
        
        # Copy default data directory contents if this is the first time
        geoserver_dir = os.path.join(GEOSERVER_BASE_DIR, f"geoserver-{GEOSERVER_VERSION}")
        default_data_dir = os.path.join(geoserver_dir, "data_dir")
        
        if os.path.exists(default_data_dir):
            for item in os.listdir(default_data_dir):
                src = os.path.join(default_data_dir, item)
                dst = os.path.join(GEOSERVER_DATA_DIR, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            print("Data directory setup complete.")
        else:
            print("Warning: Default data directory not found. Will use empty data directory.")
    else:
        print("Data directory already exists.")

def start_geoserver():
    """Start GeoServer with the configured data directory."""
    geoserver_dir = os.path.join(GEOSERVER_BASE_DIR, f"geoserver-{GEOSERVER_VERSION}")
    startup_script = os.path.join(geoserver_dir, "bin", "startup.sh")
    
    # Make sure startup script is executable
    os.chmod(startup_script, 0o755)
    
    # Set environment variables
    env = os.environ.copy()
    env["GEOSERVER_DATA_DIR"] = os.path.abspath(GEOSERVER_DATA_DIR)
    
    print("Starting GeoServer...")
    print(f"Using data directory: {env['GEOSERVER_DATA_DIR']}")
    
    # Start GeoServer
    process = subprocess.Popen(
        [startup_script],
        env=env,
        cwd=os.path.join(geoserver_dir, "bin"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down GeoServer...")
        shutdown_script = os.path.join(geoserver_dir, "bin", "shutdown.sh")
        subprocess.run([shutdown_script], check=False)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Print startup logs
    print("GeoServer is starting. Waiting for server to become available...")
    
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(line.rstrip())
        # Check if server is started
        if "GeoServer is ready" in line:
            print("\nGeoServer is ready and running!")
            print("Access the admin interface at: http://localhost:8080/geoserver/web")
            print("Press Ctrl+C to stop the server.")
            break
    
    # Keep the script running
    try:
        process.wait()
    except KeyboardInterrupt:
        pass

def main():
    """Main function to check, download and start GeoServer."""
    print("=== GeoServer Launcher for Property Mapper ===")
    
    if not check_geoserver_installed():
        print("GeoServer not found. Setting up GeoServer...")
        download_geoserver()
    else:
        print(f"GeoServer {GEOSERVER_VERSION} is already installed.")
    
    setup_data_directory()
    start_geoserver()

if __name__ == "__main__":
    main()