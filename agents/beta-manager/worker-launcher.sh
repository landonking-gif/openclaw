#!/bin/bash
# Worker launcher script for Beta Manager

cd /Users/landonking/openclaw-army

# Start worker agents on specified ports
echo "Starting general-1 on port 18811..."
npx openclaw agent start general-1 --port 18811 --daemon &

echo "Starting general-2 on port 18812..."  
npx openclaw agent start general-2 --port 18812 --daemon &

echo "Starting general-3 on port 18813..."
npx openclaw agent start general-3 --port 18813 --daemon &

echo "Starting general-4 on port 18814..."
npx openclaw agent start general-4 --port 18814 --daemon &

echo "All workers launched."
wait
