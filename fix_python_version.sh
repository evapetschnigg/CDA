#!/bin/bash
# Script to fix Python version in otreezip after running 'otree zip'
# Usage: ./fix_python_version.sh

echo "Fixing Python version in CDA_3.otreezip..."

python3 << 'PYTHON_SCRIPT'
import tarfile
import os
import shutil

if not os.path.exists('CDA_3.otreezip'):
    print("❌ CDA_3.otreezip not found!")
    exit(1)

# Extract the archive
with tarfile.open('CDA_3.otreezip', 'r:gz') as tar:
    tar.extractall('temp_extract')

# Remove old runtime.txt if it exists (otree zip creates it then deletes it)
runtime_path = 'temp_extract/runtime.txt'
if os.path.exists(runtime_path):
    os.remove(runtime_path)
    print("✅ Removed old runtime.txt")

# Create/update .python-version file
python_version_path = 'temp_extract/.python-version'
with open(python_version_path, 'w') as f:
    f.write('3.11\n')
print("✅ Updated .python-version to: 3.11")

# Recreate the archive
with tarfile.open('CDA_3.otreezip', 'w:gz') as tar:
    tar.add('temp_extract', arcname='.')

# Cleanup
shutil.rmtree('temp_extract')

print("✅ Successfully updated CDA_3.otreezip with Python 3.11")
PYTHON_SCRIPT

echo "Done! CDA_3.otreezip is ready to upload."
