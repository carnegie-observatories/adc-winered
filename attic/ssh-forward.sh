#!/bin/bash
# Forward ADC ports from officevpn to localhost
#
# Usage: ./ssh-forward.sh [start|stop|status]
#
# Ports forwarded:
#   5000 - ADC server (FastAPI)
#   5800 - TCS simulator

HOST="officevpn"
PORTS="5000 5800"
PID_FILE="/tmp/ssh-forward-adc.pid"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Already running (PID $(cat "$PID_FILE"))"
        return 1
    fi
    
    echo "Starting SSH port forwarding to $HOST..."
    ssh -N -f \
        -L 5000:localhost:5000 \
        -L 5800:localhost:5800 \
        "$HOST"
    
    # Find the SSH process we just started
    PID=$(pgrep -f "ssh -N.*$HOST" | tail -1)
    if [ -n "$PID" ]; then
        echo "$PID" > "$PID_FILE"
        echo "Forwarding active (PID $PID)"
        echo "  http://localhost:5000 -> ADC server"
        echo "  localhost:5800 -> TCS simulator"
    else
        echo "Failed to start SSH tunnel"
        return 1
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill "$PID" 2>/dev/null; then
            echo "Stopped SSH tunnel (PID $PID)"
            rm "$PID_FILE"
        else
            echo "Process not running, cleaning up"
            rm "$PID_FILE"
        fi
    else
        # Try to find and kill any matching process
        pkill -f "ssh -N.*$HOST" && echo "Stopped SSH tunnel" || echo "No tunnel running"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Running (PID $(cat "$PID_FILE"))"
        echo "Forwarded ports:"
        for PORT in $PORTS; do
            if nc -z localhost "$PORT" 2>/dev/null; then
                echo "  :$PORT ✓"
            else
                echo "  :$PORT ✗"
            fi
        done
    else
        echo "Not running"
    fi
}

case "${1:-start}" in
    start)  start ;;
    stop)   stop ;;
    status) status ;;
    *)      echo "Usage: $0 [start|stop|status]"; exit 1 ;;
esac
