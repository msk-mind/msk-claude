#!/bin/bash
# Make sure a LiteLLM proxy is reachable, starting one in the background if needed.
# Source this file; on success it exports LITELLM_HOST, LITELLM_PORT and
# MSK_PROXY_KEY (the secret clients send to the proxy).
#
# Also:
#   - stops with instructions if the session token in .auth.env is expired
#   - restarts a background proxy on this machine when .auth.env, the config or
#     the callbacks changed after it started (the proxy only reads them at startup)
#
# Proxy state lives in .proxy/<hostname>/ so machines sharing this directory
# (e.g. a shared home on a cluster) never overwrite each other's records.

_EP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_EP_STATE_ROOT="$_EP_DIR/.proxy"
_EP_STATE_DIR="$_EP_STATE_ROOT/$(hostname)"
_EP_INFO_FILE="$_EP_STATE_DIR/server_info"
_EP_LOG_FILE="$_EP_STATE_DIR/proxy.log"
_EP_PID_FILE="$_EP_STATE_DIR/proxy.pid"
_EP_LOCK_FILE="$_EP_STATE_DIR/proxy.lock"
_EP_WATCHED_FILES=("$_EP_DIR/.auth.env" "$_EP_DIR/litellm_config.yaml" "$_EP_DIR/custom_callbacks.py" "$_EP_DIR/.litellm_master_key")
_EP_STARTUP_TIMEOUT=120

# Reads a server_info file into LITELLM_HOST / LITELLM_PORT / _EP_BIND
_ep_read_server_info() {
    local hostname="" port="" bind=""
    LITELLM_HOST="" LITELLM_PORT="" _EP_BIND=""
    [ -f "$1" ] || return 1
    source "$1"
    LITELLM_PORT="$port"
    _EP_BIND="$bind"
    # A proxy listening on localhost is only reachable from its own machine
    if [ "$bind" = "127.0.0.1" ]; then
        [ "$hostname" = "$(hostname)" ] && LITELLM_HOST="127.0.0.1"
    else
        LITELLM_HOST="$hostname"
    fi
}

# Prints ok (our proxy, key accepted), foreign (reachable but rejects our key) or down.
# LiteLLM answers 400 rather than 401 for some keys it doesn't recognize.
_ep_probe() {
    [ -n "$1" ] && [ -n "$2" ] || { echo down; return; }
    local code
    code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' \
        -H "Authorization: Bearer $MSK_PROXY_KEY" "http://$1:$2/v1/models")
    case "$code" in
        200) echo ok ;;
        400|401|403) echo foreign ;;
        *) echo down ;;
    esac
}

# Prints the first watched file modified after the given server_info was written
_ep_changed_since_start() {
    local f
    for f in "${_EP_WATCHED_FILES[@]}"; do
        if [ -f "$f" ] && [ "$f" -nt "$1" ]; then
            basename "$f"
            return 0
        fi
    done
    return 1
}

# Succeeds if this machine has a background proxy started by these scripts
_ep_owns_proxy() {
    [ -f "$_EP_PID_FILE" ] || return 1
    local host pid
    read -r host pid < "$_EP_PID_FILE"
    [ "$host" = "$(hostname)" ] && kill -0 "$pid" 2>/dev/null
}

# Earlier versions kept a single set of state files at the top level. Stop a
# background proxy recorded there on this machine, then drop those files.
_ep_migrate_legacy_state() {
    local legacy_pid="$_EP_DIR/.litellm_proxy.pid" host pid
    if [ -f "$legacy_pid" ]; then
        read -r host pid < "$legacy_pid"
        [ "$host" = "$(hostname)" ] || return 0
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping the proxy started by an earlier version of these scripts (pid $pid)..."
            kill -- -"$pid" 2>/dev/null || kill "$pid"
        fi
    fi
    rm -f "$legacy_pid" "$_EP_DIR/.litellm_server_info" "$_EP_DIR/.litellm_port" \
        "$_EP_DIR/.litellm_proxy.log" "$_EP_DIR/.litellm_proxy.lock"
}

# Looks for a key-accepting proxy that another machine started with MSK_PROXY_BIND=0.0.0.0
_ep_find_remote_proxy() {
    local info
    for info in "$_EP_STATE_ROOT"/*/server_info; do
        [ -f "$info" ] && [ "$info" != "$_EP_INFO_FILE" ] || continue
        _ep_read_server_info "$info"
        [ "$_EP_BIND" = "127.0.0.1" ] && continue
        if [ "$(_ep_probe "$LITELLM_HOST" "$LITELLM_PORT")" = ok ]; then
            echo "Using the LiteLLM proxy on $LITELLM_HOST at http://$LITELLM_HOST:$LITELLM_PORT"
            if changed=$(_ep_changed_since_start "$info"); then
                echo "Warning: $changed changed after that proxy started; restart it on $LITELLM_HOST to pick up the change."
            fi
            return 0
        fi
    done
    return 1
}

_ep_start_proxy() {
    # Never leave an earlier background proxy of ours running untracked
    if _ep_owns_proxy; then
        "$_EP_DIR/stop_litellm_proxy.sh" > /dev/null
    fi

    echo "Starting a new proxy on $(hostname) (log: $_EP_LOG_FILE)..."

    # Remove stale info so we wait for the new proxy to write its own
    rm -f "$_EP_INFO_FILE" "$_EP_PID_FILE" "$_EP_LOG_FILE"

    # Keep the log and the files the proxy writes private. The inner shell
    # records its own pid before exec'ing the proxy, so the pid file names the
    # real proxy even when setsid has to fork (e.g. under job control).
    local old_umask pid="" waited=0
    old_umask=$(umask)
    umask 077
    MSK_PROXY_STATE_DIR="$_EP_STATE_DIR" nohup setsid bash -c \
        'echo "$(hostname) $$" > "$1"; exec "$2"' _ "$_EP_PID_FILE" "$_EP_DIR/start_litellm_proxy.sh" \
        > "$_EP_LOG_FILE" 2>&1 < /dev/null &
    umask "$old_umask"

    while [ $waited -lt $_EP_STARTUP_TIMEOUT ]; do
        [ -z "$pid" ] && [ -f "$_EP_PID_FILE" ] && read -r _ pid < "$_EP_PID_FILE"
        if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
            echo "Error: LiteLLM proxy exited during startup. Last log lines:"
            tail -20 "$_EP_LOG_FILE"
            rm -f "$_EP_PID_FILE"
            return 1
        fi
        if _ep_read_server_info "$_EP_INFO_FILE" &&
            [ "$(_ep_probe "$LITELLM_HOST" "$LITELLM_PORT")" = ok ]; then
            echo "LiteLLM proxy started at http://$LITELLM_HOST:$LITELLM_PORT (pid $pid)"
            echo "It keeps running after you exit; stop it with $_EP_DIR/stop_litellm_proxy.sh"
            return 0
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

    _ep_migrate_legacy_state

    local status changed
    if _ep_read_server_info "$_EP_INFO_FILE"; then
        status=$(_ep_probe "$LITELLM_HOST" "$LITELLM_PORT")
        if [ "$status" = ok ]; then
            if ! changed=$(_ep_changed_since_start "$_EP_INFO_FILE"); then
                echo "LiteLLM proxy is running at http://$LITELLM_HOST:$LITELLM_PORT"
                return 0
            fi
            if ! _ep_owns_proxy; then
                echo "Warning: $changed changed after the proxy at http://$LITELLM_HOST:$LITELLM_PORT started,"
                echo "but it was not started by these scripts, so it was left running."
                echo "Restart it yourself to pick up the change."
                return 0
            fi
            echo "$changed changed since the proxy started; restarting it..."
        elif [ "$status" = foreign ]; then
            echo "The proxy at http://$LITELLM_HOST:$LITELLM_PORT rejected this key; replacing it..."
        else
            echo "LiteLLM proxy not reachable at http://$LITELLM_HOST:$LITELLM_PORT"
        fi
    elif _ep_find_remote_proxy; then
        return 0
    fi

    _ep_start_proxy
}

# Serialize so two launches at once on this machine don't both start a proxy
mkdir -p "$_EP_STATE_DIR" && chmod 700 "$_EP_STATE_ROOT" "$_EP_STATE_DIR"
exec {_ep_lock_fd}> "$_EP_LOCK_FILE"
flock "$_ep_lock_fd"
_ep_ensure_proxy
_ep_status=$?
flock -u "$_ep_lock_fd"
exec {_ep_lock_fd}>&-

[ $_ep_status -eq 0 ] || return 1 2>/dev/null || exit 1
export LITELLM_HOST LITELLM_PORT MSK_PROXY_KEY
