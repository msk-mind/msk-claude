#!/bin/bash
# Make sure a LiteLLM proxy is reachable, starting one in the background if needed.
# Source this file; on success it exports LITELLM_HOST, LITELLM_PORT and
# MSK_PROXY_KEY (the secret clients send to the proxy).
#
# Also:
#   - stops with instructions if the session token in .auth.env is expired
#   - restarts a background proxy on this machine when .auth.env, the config or
#     the callbacks changed after it started (the proxy only reads them at startup)

_EP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_EP_INFO_FILE="$_EP_DIR/.litellm_server_info"
_EP_PORT_FILE="$_EP_DIR/.litellm_port"
_EP_LOG_FILE="$_EP_DIR/.litellm_proxy.log"
_EP_PID_FILE="$_EP_DIR/.litellm_proxy.pid"
_EP_LOCK_FILE="$_EP_DIR/.litellm_proxy.lock"
_EP_WATCHED_FILES=("$_EP_DIR/.auth.env" "$_EP_DIR/litellm_config.yaml" "$_EP_DIR/custom_callbacks.py" "$_EP_DIR/.litellm_master_key")
_EP_STARTUP_TIMEOUT=120

_ep_read_server_info() {
    hostname="" port="" bind=""
    if [ -f "$_EP_INFO_FILE" ]; then
        source "$_EP_INFO_FILE"
        LITELLM_HOST="${hostname:-localhost}"
        LITELLM_PORT="${port:-22660}"
        # A proxy listening on localhost is only reachable from its own machine
        if [ "$bind" = "127.0.0.1" ]; then
            if [ "$hostname" = "$(hostname)" ]; then
                LITELLM_HOST="127.0.0.1"
            else
                LITELLM_HOST=""
            fi
        fi
    elif [ -f "$_EP_PORT_FILE" ]; then
        LITELLM_HOST="localhost"
        LITELLM_PORT=$(cat "$_EP_PORT_FILE")
    else
        LITELLM_HOST="localhost"
        LITELLM_PORT=22660
    fi
}

# Prints ok (our proxy, key accepted), foreign (reachable but rejects our key) or down.
# LiteLLM answers 400 rather than 401 for some keys it doesn't recognize.
_ep_probe() {
    [ -n "$1" ] || { echo down; return; }
    local code
    code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' \
        -H "Authorization: Bearer $MSK_PROXY_KEY" "http://$1:$2/v1/models")
    case "$code" in
        200) echo ok ;;
        400|401|403) echo foreign ;;
        *) echo down ;;
    esac
}

# Prints the first watched file modified after the proxy started, if any
_ep_changed_since_start() {
    local f
    for f in "${_EP_WATCHED_FILES[@]}"; do
        if [ -f "$f" ] && [ "$f" -nt "$_EP_INFO_FILE" ]; then
            basename "$f"
            return 0
        fi
    done
    return 1
}

# Succeeds if the background proxy recorded in the pid file runs on this machine
_ep_owns_proxy() {
    [ -f "$_EP_PID_FILE" ] || return 1
    local host pid
    read -r host pid < "$_EP_PID_FILE"
    [ "$host" = "$(hostname)" ] && kill -0 "$pid" 2>/dev/null
}

_ep_start_proxy() {
    # Never leave an earlier background proxy of ours running untracked
    if _ep_owns_proxy; then
        "$_EP_DIR/stop_litellm_proxy.sh" > /dev/null
    fi

    echo "Starting a new proxy on $(hostname) (log: $_EP_LOG_FILE)..."

    # Remove stale info so we wait for the new proxy to write its own
    rm -f "$_EP_INFO_FILE" "$_EP_PORT_FILE" "$_EP_LOG_FILE"

    # Keep the log and the files the proxy writes private
    local old_umask pid
    old_umask=$(umask)
    umask 077
    nohup setsid "$_EP_DIR/start_litellm_proxy.sh" > "$_EP_LOG_FILE" 2>&1 < /dev/null &
    pid=$!
    echo "$(hostname) $pid" > "$_EP_PID_FILE"
    umask "$old_umask"

    local waited=0
    while [ $waited -lt $_EP_STARTUP_TIMEOUT ]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "Error: LiteLLM proxy exited during startup. Last log lines:"
            tail -20 "$_EP_LOG_FILE"
            rm -f "$_EP_PID_FILE"
            return 1
        fi
        if [ -f "$_EP_INFO_FILE" ]; then
            _ep_read_server_info
            if [ "$(_ep_probe "$LITELLM_HOST" "$LITELLM_PORT")" = ok ]; then
                echo "LiteLLM proxy started at http://$LITELLM_HOST:$LITELLM_PORT (pid $pid)"
                echo "It keeps running after you exit; stop it with $_EP_DIR/stop_litellm_proxy.sh"
                return 0
            fi
        fi
        sleep 2
        waited=$((waited + 2))
    done

    echo "Error: LiteLLM proxy did not become healthy within ${_EP_STARTUP_TIMEOUT}s. Last log lines:"
    tail -20 "$_EP_LOG_FILE"
    return 1
}

_ep_ensure_proxy() {
    python3 "$_EP_DIR/aiportal.py" token-check || return 1
    MSK_PROXY_KEY="$(python3 "$_EP_DIR/aiportal.py" proxy-key)" || return 1

    _ep_read_server_info
    local status changed
    status=$(_ep_probe "$LITELLM_HOST" "$LITELLM_PORT")

    if [ "$status" = ok ]; then
        if ! changed=$(_ep_changed_since_start); then
            echo "LiteLLM proxy is running at http://$LITELLM_HOST:$LITELLM_PORT"
            return 0
        fi
        if _ep_owns_proxy; then
            echo "$changed changed since the proxy started; restarting it..."
            "$_EP_DIR/stop_litellm_proxy.sh" > /dev/null
        else
            echo "Warning: $changed changed after the proxy at http://$LITELLM_HOST:$LITELLM_PORT started,"
            echo "but it was not started by these scripts on this machine, so it was left running."
            echo "Restart it yourself to pick up the change."
            return 0
        fi
    elif [ "$status" = foreign ] && _ep_owns_proxy; then
        echo "The background proxy uses an old key; restarting it..."
        "$_EP_DIR/stop_litellm_proxy.sh" > /dev/null
    elif [ "$status" = foreign ]; then
        echo "The proxy at http://$LITELLM_HOST:$LITELLM_PORT rejected this key (not one of yours, or an old one)."
    elif [ -z "$LITELLM_HOST" ]; then
        echo "The recorded proxy on $hostname only accepts local connections."
    else
        echo "LiteLLM proxy not reachable at http://$LITELLM_HOST:$LITELLM_PORT"
    fi

    _ep_start_proxy
}

# Serialize so two launches at once don't both start a proxy
exec {_ep_lock_fd}> "$_EP_LOCK_FILE"
flock "$_ep_lock_fd"
_ep_ensure_proxy
_ep_status=$?
flock -u "$_ep_lock_fd"
exec {_ep_lock_fd}>&-

[ $_ep_status -eq 0 ] || return 1 2>/dev/null || exit 1
export LITELLM_HOST LITELLM_PORT MSK_PROXY_KEY
