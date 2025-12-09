#!/bin/bash
# Monitor address generation progress

echo "🔍 Monitoring Address Generation..."
echo "=================================="
echo ""

while true; do
    clear
    echo "📊 Address Generation Status"
    echo "============================"
    echo ""
    
    # Check if cache file exists
    if [ -f "validated_address_cache.json" ]; then
        echo "✅ Cache file: EXISTS"
        echo ""
        echo "📝 Current addresses:"
        cat validated_address_cache.json | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for country, addresses in data.get('addresses', {}).items():
        print(f'   {country}: {len(addresses)} addresses')
        if len(addresses) > 0:
            print(f'      Sample: {addresses[0][:60]}...')
except:
    print('   (parsing...)')
" 2>/dev/null || echo "   (checking...)"
    else
        echo "⏳ Cache file: NOT YET CREATED"
        echo "   (Script is still generating addresses...)"
    fi
    
    echo ""
    echo "🔄 Running processes:"
    ps aux | grep "generate_validated_address_cache" | grep -v grep | awk '{printf "   PID: %-6s | CPU: %5s%% | Time: %s\n", $2, $3, $10}' || echo "   (no processes found)"
    
    echo ""
    echo "📋 Recent log output:"
    tail -10 /tmp/address_gen.log 2>/dev/null | grep -E "(ACCEPTED|REJECTED|Processing|Querying)" | tail -5 || echo "   (checking log...)"
    
    echo ""
    echo "⏰ Last updated: $(date '+%H:%M:%S')"
    echo ""
    echo "Press Ctrl+C to stop monitoring"
    
    sleep 5
done

