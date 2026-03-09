#!/bin/bash
# Build script to prepare frontend static files for Docker build
# This copies the frontend dist to backend/static so Docker can include it

set -e

echo "Building frontend..."
cd ../frontend
npm install
npm run build

echo "Copying frontend dist to backend/static..."
cd ../backend
rm -rf static
cp -r ../frontend/dist ./static

echo "Frontend static files ready for Docker build"
