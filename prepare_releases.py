#!/usr/bin/env python3
"""
Script to prepare releases by generating build information.
Scans the releases folder and generates build.txt with BUILD_DESC and BUILD_DATE.
"""

import os
import sys
import subprocess
import re
import shutil
import tarfile
import zipfile
import tempfile
from pathlib import Path


def find_repo_root():
    """Find the repository root directory."""
    # Get the directory where this script is located
    script_dir = Path(__file__).resolve().parent
    return script_dir


def ensure_releases_dir(repo_path):
    """Ensure the releases directory exists."""
    releases_dir = repo_path / "releases"
    releases_dir.mkdir(exist_ok=True)
    return releases_dir


def run_genbuild_script(repo_path):
    """Run the genbuild.sh script to generate build.txt."""
    genbuild_script = repo_path / "share" / "genbuild.sh"
    build_txt_path = repo_path / "releases" / "build.txt"
    
    if not genbuild_script.exists():
        print(f"Error: genbuild.sh not found at {genbuild_script}")
        sys.exit(1)
    
    # Make sure genbuild.sh is executable
    os.chmod(genbuild_script, 0o755)
    
    # Run: $repo_path/share/genbuild.sh $repo_path/releases/build.txt $repo_path .
    cmd = [
        str(genbuild_script),
        str(build_txt_path),
        str(repo_path),
        "."
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error running genbuild.sh:")
        print(result.stderr)
        sys.exit(1)
    
    return build_txt_path


def parse_build_txt(build_txt_path):
    """Parse build.txt and extract BUILD_DESC and BUILD_DATE."""
    if not build_txt_path.exists():
        print(f"Error: build.txt not found at {build_txt_path}")
        sys.exit(1)
    
    build_desc = None
    build_date = None
    
    with open(build_txt_path, 'r') as f:
        content = f.read()
        
        # Extract BUILD_DESC
        desc_match = re.search(r'#define BUILD_DESC\s+"([^"]+)"', content)
        if desc_match:
            build_desc = desc_match.group(1)
        
        # Extract BUILD_DATE
        date_match = re.search(r'#define BUILD_DATE\s+"([^"]+)"', content)
        if date_match:
            build_date = date_match.group(1)
    
    return build_desc, build_date


def scan_releases_dir(releases_dir):
    """Scan the releases directory for macOS, Windows, and focal releases."""
    if not releases_dir.exists():
        print(f"Warning: releases directory does not exist at {releases_dir}")
        return []
    
    releases = []
    for item in releases_dir.iterdir():
        if item.is_dir():
            releases.append(item.name)
    
    return releases


def extract_version(build_desc):
    """Extract version from BUILD_DESC by removing leading 'v'."""
    if not build_desc:
        return None
    if build_desc.startswith('v'):
        return build_desc[1:]
    return build_desc


def validate_release_files(releases_dir, build_desc):
    """Validate that all required files exist in release folders."""
    if not build_desc:
        print("Error: BUILD_DESC is not available, cannot validate release files")
        sys.exit(1)
    
    version = extract_version(build_desc)
    if not version:
        print("Error: Could not extract version from BUILD_DESC")
        sys.exit(1)
    
    print("\nValidating release files...")
    
    # Define required files for each platform
    required_files = {
        'focal': [
            'wallet-utility',
            'komodod',
            'komodo-tx',
            'komodo-cli'
        ],
        'windows': [
            'wallet-utility.exe',
            'komodod.exe',
            'komodo-tx.exe',
            'komodo-cli.exe'
        ]
    }
    
    missing_files = []
    
    for platform, files in required_files.items():
        platform_dir = releases_dir / platform
        
        if not platform_dir.exists():
            print(f"Error: {platform} directory does not exist at {platform_dir}")
            sys.exit(1)
        
        print(f"\nChecking {platform} folder:")
        for filename in files:
            file_path = platform_dir / filename
            if file_path.exists():
                print(f"  ✓ {filename}")
            else:
                print(f"  ✗ {filename} - MISSING")
                missing_files.append(f"{platform}/{filename}")
    
    if missing_files:
        print(f"\nError: Missing required files:")
        for missing_file in missing_files:
            print(f"  - {missing_file}")
        sys.exit(1)
    
    print("\n✓ All required release files are present")


def create_komodo_conf(temp_dir):
    """Create komodo.conf file in the temporary directory."""
    komodo_conf_path = temp_dir / "komodo.conf"
    komodo_conf_content = """txindex=1
onlynet=ipv4
rpcuser=komodo
rpcpassword=local321
rpcallowip=127.0.0.1
rpcbind=127.0.0.1
# rpc server turned off by default for security purposes
server=0
"""
    with open(komodo_conf_path, 'w') as f:
        f.write(komodo_conf_content)
    print(f"  Created komodo.conf")


def prepare_archive(repo_path, releases_dir, platform, build_desc):
    """Prepare archive for a specific platform."""
    print(f"\nPreparing archive for {platform}...")
    
    platform_dir = releases_dir / platform
    if not platform_dir.exists():
        print(f"Error: {platform} directory does not exist at {platform_dir}")
        sys.exit(1)
    
    # Create temporary directory
    with tempfile.TemporaryDirectory(prefix=f"komodo-release-{platform}-") as temp_dir:
        temp_path = Path(temp_dir)
        print(f"  Created temporary directory: {temp_path}")
        
        # Copy all files from platform directory to temporary directory
        # Exclude .dmg files for macOS (they are copied separately)
        print(f"  Copying files from {platform_dir}...")
        for item in platform_dir.iterdir():
            if item.is_file():
                # Skip .dmg files for macOS
                if platform == 'macos' and item.suffix == '.dmg':
                    print(f"    Skipped {item.name} (will be copied separately)")
                    continue
                shutil.copy2(item, temp_path)
                print(f"    Copied {item.name}")
        
        # Create komodo.conf
        create_komodo_conf(temp_path)
        
        # Copy fetch-params files
        zcutil_dir = repo_path / "zcutil"
        if platform in ['focal', 'macos']:
            fetch_params_sh = zcutil_dir / "fetch-params.sh"
            fetch_params_alt_sh = zcutil_dir / "fetch-params-alt.sh"
            
            if fetch_params_sh.exists():
                shutil.copy2(fetch_params_sh, temp_path)
                os.chmod(temp_path / "fetch-params.sh", 0o755)
                print(f"    Copied fetch-params.sh")
            else:
                print(f"    Warning: fetch-params.sh not found at {fetch_params_sh}")
            
            if fetch_params_alt_sh.exists():
                shutil.copy2(fetch_params_alt_sh, temp_path)
                os.chmod(temp_path / "fetch-params-alt.sh", 0o755)
                print(f"    Copied fetch-params-alt.sh")
            else:
                print(f"    Warning: fetch-params-alt.sh not found at {fetch_params_alt_sh}")
        
        elif platform == 'windows':
            fetch_params_bat = zcutil_dir / "fetch-params.bat"
            
            if fetch_params_bat.exists():
                shutil.copy2(fetch_params_bat, temp_path)
                print(f"    Copied fetch-params.bat")
            else:
                print(f"    Warning: fetch-params.bat not found at {fetch_params_bat}")
        
        version = extract_version(build_desc)
        if not version:
            print("Error: Could not extract version from BUILD_DESC")
            sys.exit(1)
        
        # Create archive
        if platform == 'focal':
            archive_name = f"komodo-{version}-linux.tar.gz"
            archive_path = releases_dir / archive_name
            
            print(f"  Creating archive {archive_name}...")
            with tarfile.open(archive_path, "w:gz") as tar:
                for item in temp_path.iterdir():
                    tar.add(item, arcname=item.name)
            print(f"  ✓ Created {archive_name}")
        
        elif platform == 'windows':
            archive_name = f"komodo-{version}-win.zip"
            archive_path = releases_dir / archive_name
            
            print(f"  Creating archive {archive_name}...")
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for item in temp_path.iterdir():
                    zipf.write(item, arcname=item.name)
            print(f"  ✓ Created {archive_name}")
        
        elif platform == 'macos':
            archive_name = "komodo-qt-mac.zip"
            archive_path = releases_dir / archive_name
            
            print(f"  Creating archive {archive_name}...")
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for item in temp_path.iterdir():
                    zipf.write(item, arcname=item.name)
            print(f"  ✓ Created {archive_name}")
            
            # Copy .dmg file to releases
            version = extract_version(build_desc)
            dmg_name = f"KomodoOcean-{version}.dmg"
            dmg_source = platform_dir / dmg_name
            dmg_dest = releases_dir / dmg_name
            
            if dmg_source.exists():
                shutil.copy2(dmg_source, dmg_dest)
                print(f"  ✓ Copied {dmg_name} to releases")
            else:
                print(f"  Error: {dmg_name} not found at {dmg_source}")
                sys.exit(1)


def sign_releases(repo_path, releases_dir):
    """Copy and run sign-release.sh script in releases directory."""
    print("\nSigning releases...")
    
    sign_script_source = repo_path / "contrib" / "sign-release.sh"
    sign_script_dest = releases_dir / "sign-release.sh"
    
    if not sign_script_source.exists():
        print(f"Error: sign-release.sh not found at {sign_script_source}")
        sys.exit(1)
    
    # Copy sign-release.sh to releases directory
    shutil.copy2(sign_script_source, sign_script_dest)
    os.chmod(sign_script_dest, 0o755)
    print(f"  Copied sign-release.sh to releases directory")
    
    # Run sign-release.sh from releases directory
    print(f"  Running sign-release.sh...")
    result = subprocess.run(
        [str(sign_script_dest)],
        cwd=str(releases_dir),
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error running sign-release.sh:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    
    print(f"  ✓ Signing completed successfully")


def main():
    """Main function."""
    print("Preparing releases...")
    
    # Find repository root
    repo_path = find_repo_root()
    print(f"Repository root: {repo_path}")
    
    # Ensure releases directory exists
    releases_dir = ensure_releases_dir(repo_path)
    print(f"Releases directory: {releases_dir}")
    
    # Scan releases directory
    releases = scan_releases_dir(releases_dir)
    if releases:
        print(f"Found releases: {', '.join(releases)}")
    else:
        print("No releases found in releases directory")
    
    # Run genbuild.sh script
    build_txt_path = run_genbuild_script(repo_path)
    print(f"Generated build.txt at: {build_txt_path}")
    
    # Parse build.txt
    build_desc, build_date = parse_build_txt(build_txt_path)
    
    # Print extracted values
    print("\nExtracted build information:")
    if build_desc:
        print(f"BUILD_DESC: {build_desc}")
    else:
        print("BUILD_DESC: Not found")
    
    if build_date:
        print(f"BUILD_DATE: {build_date}")
    else:
        print("BUILD_DATE: Not found")
    
    # Validate release files
    validate_release_files(releases_dir, build_desc)
    
    # Prepare archives for each platform
    platforms = ['focal', 'windows']
    for platform in platforms:
        prepare_archive(repo_path, releases_dir, platform, build_desc)
    
    # Sign releases
    sign_releases(repo_path, releases_dir)
    
    print("\n✓ Release preparation completed successfully!")
    
    return build_desc, build_date


if __name__ == "__main__":
    main()
