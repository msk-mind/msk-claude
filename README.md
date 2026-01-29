# MSK Claude CLI Connector

Connect the Claude CLI to MSK's Open WebUI instance at `https://chat.aicopilot.aws.mskcc.org` using a LiteLLM proxy.

## Overview

This project provides a LiteLLM proxy that translates between the Claude CLI and MSK's Open WebUI, allowing you to use Claude Code CLI with MSK's internal AI infrastructure.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Your Session Token

1. Log in to https://chat.aicopilot.aws.mskcc.org in your browser
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies
4. Copy the value of the `token` cookie

### 3. Create Authentication File

Create a `.auth.env` file in this directory:

```bash
export WEBUI_SESSION_TOKEN='your-token-here'
```

**Note:** Add `.auth.env` to `.gitignore` to avoid committing your token.

## Usage

### Start the LiteLLM Proxy

The proxy runs on port 22660 by default and automatically loads your session token:

```bash
./start_litellm_proxy.sh
```

The proxy will:
- Listen on `http://localhost:22660`
- Connect to MSK WebUI at `https://chat.aicopilot.aws.mskcc.org`
- Handle SSL verification for the internal MSK server
- Support all available Claude models

### Use Claude CLI

In a separate terminal, use the provided wrapper script:

```bash
# Use default model (claude-sonnet-4.5) in current directory
./connect_claude.sh

# Use a specific model
./connect_claude.sh -m claude-sonnet-4

# Work in a specific directory
./connect_claude.sh /path/to/project

# Use specific model in specific directory
./connect_claude.sh -m claude-3.7-sonnet /path/to/project
```

Available models:
- `claude-sonnet-4.5` (default) - 65,536 max tokens
- `claude-sonnet-4` - 65,536 max tokens
- `claude-3.7-sonnet` - 65,536 max tokens
- `claude-3.5-sonnet` - 8,192 max tokens

**Note:** Haiku model requests automatically fallback to Claude Sonnet 4.5 since Haiku models are not available on the MSK WebUI.

## Configuration

### LiteLLM Configuration (`litellm_config.yaml`)

The proxy is configured with:
- Model mappings to MSK WebUI Bedrock models
- Per-model token limits
- SSL verification disabled for internal MSK server
- Environment variable substitution for session token

### Environment Setup (`setup_claude_env.sh`)

Configures Claude CLI to use the LiteLLM proxy:
- Sets `ANTHROPIC_AUTH_TOKEN` for authentication
- Configures base URL to `http://localhost:22660`
- Disables telemetry and error reporting

## Architecture

```
Claude CLI → LiteLLM Proxy (localhost:22660) → MSK Open WebUI (HTTPS) → Bedrock Claude Models
```

The LiteLLM proxy:
1. Receives requests from Claude CLI in Anthropic API format
2. Translates them to OpenAI-compatible format
3. Forwards to MSK WebUI with your session token
4. Handles SSL verification bypass for internal MSK certificates
5. Returns responses in the format Claude CLI expects

## Troubleshooting

### Session Token Expired

If you get 401 errors, your session token may have expired. Get a new token from the browser and update `.auth.env`.

### SSL Certificate Errors

The proxy automatically handles SSL verification for the internal MSK server. If you still see SSL errors, make sure you're running the latest version of the proxy.

### Model Not Available

Some Claude models (like Haiku) are not available on MSK WebUI. The proxy automatically falls back to Claude Sonnet 4.5 for these requests.

### Port Already in Use

If port 22660 is already in use, you can change it in:
1. `start_litellm_proxy.sh` (the `--port` parameter)
2. `setup_claude_env.sh` (the `ANTHROPIC_BASE_URL`)

## Files

- `start_litellm_proxy.sh` - Starts the LiteLLM proxy server
- `start_litellm.py` - Python wrapper that patches SSL verification
- `litellm_config.yaml` - LiteLLM proxy configuration
- `connect_claude.sh` - Wrapper to launch Claude CLI with proxy
- `setup_claude_env.sh` - Environment configuration for Claude CLI
- `.auth.env` - Your session token (create this, not in git)
- `requirements.txt` - Python dependencies

## Security Notes

- Never commit `.auth.env` to git
- Session tokens expire periodically and need to be refreshed
- The proxy runs locally and only you can access it
- SSL verification is disabled only for the MSK internal server connection
