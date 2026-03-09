#!/bin/bash
# Fix venv permissions and reinstall requirements

cd "$(dirname "$0")"

echo "Fixing venv ownership..."
sudo chown -R vachana.visweswaraiah:staff venv/

echo "Activating venv and installing requirements..."
source venv/bin/activate
pip install -r requirements.txt

echo "Done!"






