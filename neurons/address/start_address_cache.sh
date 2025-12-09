#!/bin/bash

echo "=========================================="
echo "🚀 Starting Address Cache Generation"
echo "=========================================="
echo ""
echo "This will:"
echo "  - Generate addresses for all countries"
echo "  - Save logs to: address_cache.log"
echo "  - Show real-time output"
echo ""
echo "To view thread logs in tmux:"
echo "  tail -f address_cache.log | grep 'Thread- 1'"
echo ""
echo "=========================================="
echo ""

cd /Users/prasad/cursor/MIID-subnet
python3 generate_address_cache.py 2>&1 | tee address_cache.log
