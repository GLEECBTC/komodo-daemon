#!/usr/bin/env python3
"""
Script to check dependency URL availability.
Checks if files are accessible via URLs specified in .mk files from depends/packages.

Copyright (c) 2025-2026 Decker

This script was written by Decker with assistance from AI (Claude via Cursor IDE).

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

For the full license text, see: https://opensource.org/licenses/MIT
"""

import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple, List

try:
    import requests
except ImportError:
    print("Error: requests library is required. Install it with: pip install requests")
    sys.exit(1)


# User-Agent for the latest Mozilla browser on Windows
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ANSI color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'


def parse_mk_file(file_path: Path) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Parses .mk file and extracts variables.
    Returns a tuple (package_name, variables), where variables is a dictionary with variables,
    where keys are variable names without the $(package)_ prefix.
    """
    variables = {}
    package_name = None
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Extract package name
    for line in lines:
        line = line.strip()
        if line.startswith('package='):
            package_name = line.split('=', 1)[1].strip()
            break
    
    if not package_name:
        return None, {}
    
    # Extract all variables of the form $(package)_variable=value
    # Process line by line for more accurate parsing
    current_var = None
    current_value = []
    in_conditional = False
    conditional_depth = 0
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            continue
        
        # Handle conditional constructs
        if stripped.startswith('if') or stripped.startswith('ifeq') or stripped.startswith('ifneq'):
            in_conditional = True
            conditional_depth += 1
            continue
        elif stripped.startswith('else'):
            continue
        elif stripped.startswith('endif'):
            conditional_depth -= 1
            if conditional_depth == 0:
                in_conditional = False
            continue
        
        # Skip define blocks
        if stripped.startswith('define ') or stripped.startswith('endef'):
            continue
        
        # Look for variables of the form $(package)_variable=value
        var_match = re.match(r'\$\(package\)_(\w+)\s*=\s*(.+)', stripped)
        if var_match:
            # Save previous variable
            if current_var:
                variables[current_var] = ' '.join(current_value).strip()
            
            current_var = var_match.group(1)
            # Take the value, but trim it at the first space after if/else/endif
            value = var_match.group(2).strip()
            # Remove conditional constructs from the value
            value = re.sub(r'\s+(if|else|endif|ifeq|ifneq).*$', '', value)
            current_value = [value]
        elif current_var and stripped and not in_conditional:
            # Continuation of variable value (multiline), but only outside conditions
            # Remove conditional constructs
            clean_line = re.sub(r'\s+(if|else|endif|ifeq|ifneq).*$', '', stripped)
            if clean_line:
                current_value.append(clean_line)
    
    # Save the last variable
    if current_var:
        variables[current_var] = ' '.join(current_value).strip()
    
    return package_name, variables


def resolve_variables(value: str, variables: Dict[str, str], package_name: str) -> str:
    """
    Resolves variables in a string, replacing $(package)_var with values.
    Handles nested variables like $($(package)_version).
    """
    result = value
    max_iterations = 20  # Protection against infinite loop
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        changed = False
        old_result = result
        
        # First replace $(package) with package name
        result = result.replace('$(package)', package_name)
        if result != old_result:
            changed = True
            old_result = result
        
        # Handle nested variables like $($(package)_version)
        # After replacing $(package) this becomes $(package_name_version)
        nested_pattern = r'\$\(([a-zA-Z_][a-zA-Z0-9_]*)_(\w+)\)'
        match = re.search(nested_pattern, result)
        if match:
            prefix = match.group(1)
            var_name = match.group(2)
            # If prefix matches package name, this is our variable
            if prefix == package_name and var_name in variables:
                result = result.replace(match.group(0), variables[var_name])
                changed = True
                continue
        
        # Replace variables of the form $(package_name_var) directly
        var_pattern = r'\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)'
        match = re.search(var_pattern, result)
        if match:
            var_key = match.group(1)
            # Check if this is a package variable (package_name_var)
            if var_key.startswith(package_name + '_'):
                var_name = var_key[len(package_name) + 1:]  # Remove package_name_ prefix
                if var_name in variables:
                    result = result.replace(match.group(0), variables[var_name])
                    changed = True
                    continue
        
        # If nothing changed, exit
        if not changed:
            break
    
    return result


def build_url(download_path: str, file_name: str) -> str:
    """
    Builds a full URL from download path and file name.
    """
    # Remove trailing slash from download_path
    download_path = download_path.rstrip('/')
    
    # If file_name starts with /, remove it
    file_name = file_name.lstrip('/')
    
    # Build URL
    if download_path.endswith('/'):
        url = download_path + file_name
    else:
        url = download_path + '/' + file_name
    
    return url


def check_url(url: str, package_name: str = None) -> Tuple[bool, int, str]:
    """
    Checks URL availability via HEAD request.
    Returns (success, status_code, message).
    Handles redirects automatically.
    
    Args:
        url: URL to check
        package_name: Package name for special handling (e.g., fontconfig with 418 status)
    """
    try:
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=30,
            headers={'User-Agent': USER_AGENT}
        )
        
        status_code = response.status_code
        
        if status_code == 200:
            return True, status_code, "Ok"
        elif status_code == 404:
            return False, status_code, "Not Found"
        elif status_code == 418 and package_name == 'fontconfig':
            # fontconfig returns 418 (I'm a teapot) but the file is actually available
            return True, status_code, "Ok (418 - special case)"
        else:
            return False, status_code, f"HTTP {status_code}"
    
    except requests.exceptions.Timeout:
        return False, 0, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, 0, "Connection Error"
    except requests.exceptions.TooManyRedirects:
        return False, 0, "Too Many Redirects"
    except requests.exceptions.RequestException as e:
        return False, 0, f"Error: {str(e)}"


def load_all_packages(depends_dir: Path) -> Dict[str, Dict[str, str]]:
    """
    Loads information about all packages to resolve cross-package references.
    """
    all_packages = {}
    for mk_file in depends_dir.glob('*.mk'):
        # Skip packages.mk as it's a package list, not a package
        # and dummy.mk as it's a test/example package
        if mk_file.name in ['packages.mk', 'dummy.mk']:
            continue
        package_name, variables = parse_mk_file(mk_file)
        if package_name:
            all_packages[package_name] = variables
    return all_packages


def resolve_cross_package_variables(value: str, package_name: str, all_packages: Dict[str, Dict[str, str]]) -> str:
    """
    Resolves variables referencing other packages (e.g., $(native_protobuf_version)).
    """
    result = value
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        changed = False
        old_result = result
        
        # Look for references to other packages of the form $(other_package_var)
        # Use a simpler pattern and parse manually
        pattern = r'\$\(([^)]+)\)'
        matches = list(re.finditer(pattern, result))
        
        for match in reversed(matches):  # Process from the end to avoid index issues
            full_var = match.group(1)
            
            # Try to find a package that matches the beginning of full_var
            matched = False
            for other_package in all_packages.keys():
                if other_package != package_name and full_var.startswith(other_package + '_'):
                    var_name = full_var[len(other_package) + 1:]  # Remove package_ prefix
                    if var_name in all_packages[other_package]:
                        # Get the value and resolve variables in it for this package
                        var_value = all_packages[other_package][var_name]
                        # Resolve variables in the value relative to the other package
                        var_value = resolve_variables(var_value, all_packages[other_package], other_package)
                        result = result[:match.start()] + var_value + result[match.end():]
                        changed = True
                        matched = True
                        break
            
            if not matched:
                # Try to parse as package_var (last underscore)
                parts = full_var.rsplit('_', 1)
                if len(parts) == 2:
                    potential_package = parts[0]
                    var_name = parts[1]
                    
                    # If this is not our package and it exists in all_packages
                    if potential_package != package_name and potential_package in all_packages:
                        if var_name in all_packages[potential_package]:
                            var_value = all_packages[potential_package][var_name]
                            var_value = resolve_variables(var_value, all_packages[potential_package], potential_package)
                            result = result[:match.start()] + var_value + result[match.end():]
                            changed = True
        
        if not changed:
            break
    
    return result


def check_dependency_file(mk_file: Path, depends_dir: Path, all_packages: Dict[str, Dict[str, str]] = None) -> Optional[Dict]:
    """
    Checks one .mk file and returns the result.
    """
    try:
        package_name, variables = parse_mk_file(mk_file)
        
        if not package_name:
            return {
                'package': mk_file.stem,
                'status': 'error',
                'message': 'Failed to determine package name'
            }
        
        # Check for required variables
        if 'download_path' not in variables:
            return {
                'package': package_name,
                'status': 'skip',
                'message': 'Missing required variable (download_path)'
            }
        
        # Use download_file if available, otherwise file_name
        # download_file is the actual filename on the server, file_name is for local storage
        # Exception: for zeromq, use file_name instead of download_file
        # because zeromq.mk has conditional blocks (mingw32 vs others) and download_file
        # contains the mingw32-specific value (v$($(package)_version).tar.gz), while
        # file_name contains the correct value for non-mingw32 builds (zeromq-$($(package)_version).tar.gz)
        if package_name == 'zeromq' and 'file_name' in variables:
            file_var = 'file_name'
        elif 'download_file' in variables:
            file_var = 'download_file'
        elif 'file_name' in variables:
            file_var = 'file_name'
        else:
            return {
                'package': package_name,
                'status': 'skip',
                'message': 'Missing required variable (download_file or file_name)'
            }
        
        # Resolve variables
        download_path = resolve_variables(variables['download_path'], variables, package_name)
        file_name = resolve_variables(variables[file_var], variables, package_name)
        
        # Resolve cross-package references if information about other packages is available
        if all_packages:
            download_path = resolve_cross_package_variables(download_path, package_name, all_packages)
            file_name = resolve_cross_package_variables(file_name, package_name, all_packages)
        
        # Check if there are unresolved variables left
        if '$(' in download_path or '$(' in file_name:
            return {
                'package': package_name,
                'status': 'skip',
                'message': 'Failed to resolve all variables (possible cross-package references)'
            }
        
        # Build URL
        url = build_url(download_path, file_name)
        
        # Check availability
        success, status_code, message = check_url(url, package_name)
        
        return {
            'package': package_name,
            'url': url,
            'status': 'ok' if success else 'error',
            'status_code': status_code,
            'message': message
        }
    
    except Exception as e:
        return {
            'package': mk_file.stem,
            'status': 'error',
            'message': f'Error processing: {str(e)}'
        }


def main():
    """
    Main script function.
    """
    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    depends_packages_dir = project_root / 'depends' / 'packages'
    
    if not depends_packages_dir.exists():
        print(f"Error: directory {depends_packages_dir} not found")
        sys.exit(1)
    
    # Find all .mk files, excluding packages.mk (it's a package list, not a package)
    # and dummy.mk (it's a test/example package)
    mk_files = sorted([f for f in depends_packages_dir.glob('*.mk') 
                       if f.name not in ['packages.mk', 'dummy.mk']])
    
    if not mk_files:
        print(f"No .mk files found in {depends_packages_dir}")
        sys.exit(1)
    
    print(f"Checking {len(mk_files)} dependency files...\n")
    
    # Load information about all packages to resolve cross-package references
    print("Loading package information...")
    all_packages = load_all_packages(depends_packages_dir)
    print(f"Loaded {len(all_packages)} packages.\n")
    
    results = []
    total_files = len(mk_files)
    
    # Process files with progress indicator
    for idx, mk_file in enumerate(mk_files, 1):
        package_name, _ = parse_mk_file(mk_file)
        package_display = package_name if package_name else mk_file.stem
        progress = f"[{idx}/{total_files}]"
        print(f"{progress} Checking {package_display}...", end=' ', flush=True)
        
        result = check_dependency_file(mk_file, depends_packages_dir, all_packages)
        if result:
            results.append(result)
            # Print result inline
            status = result['status']
            if status == 'ok':
                print(f"{GREEN}✓{RESET} Ok")
            elif status == 'error':
                message = result.get('message', 'Unknown error')
                status_code = result.get('status_code', 'N/A')
                print(f"{RED}✗{RESET} {message} (HTTP {status_code})")
            elif status == 'skip':
                message = result.get('message', 'Skipped')
                print(f"- {message}")
    
    # Print summary
    print(f"\n{'='*70}")
    
    ok_count = sum(1 for r in results if r['status'] == 'ok')
    error_count = sum(1 for r in results if r['status'] == 'error')
    skip_count = sum(1 for r in results if r['status'] == 'skip')
    
    print(f"Summary: Ok: {ok_count}, Errors: {error_count}, Skipped: {skip_count}")
    
    # Print detailed results for errors
    if error_count > 0:
        print(f"\nDetailed error information:")
        for result in results:
            if result['status'] == 'error':
                package = result['package']
                url = result.get('url', 'N/A')
                message = result.get('message', 'Unknown error')
                status_code = result.get('status_code', 'N/A')
                print(f"  {RED}✗{RESET} {package:30s} - {message} (HTTP {status_code})")
                print(f"    URL: {url}")
    
    # Return exit code
    if error_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
