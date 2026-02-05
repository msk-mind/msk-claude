# MSK Claude CLI Connector

⚠️ **This approach is very expensive so we don't recommend it (think $500 for two days of coding)**

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

The proxy automatically finds an available port starting from 22660 and saves it to `.litellm_port`:

```bash
./start_litellm_proxy.sh
```

The proxy will:
- Find the next available port (starting from 22660)
- Save the port to `.litellm_port` for the Claude CLI to use
- Listen on `http://localhost:<port>`
- Connect to MSK WebUI at `https://chat.aicopilot.aws.mskcc.org`
- Handle SSL verification for the internal MSK server
- Support all available models (Claude, GPT, Amazon Nova, Llama)

### Use Claude CLI

In a separate terminal, use the provided wrapper script:

```bash
# Use default model (claude-sonnet-4.5) in current directory
./connect_claude.sh

# Use a specific model
./connect_claude.sh -m claude-sonnet-4

# Use GPT models
./connect_claude.sh -m gpt-4o
./connect_claude.sh -m o1

# Work in a specific directory
./connect_claude.sh /path/to/project

# Use specific model in specific directory
./connect_claude.sh -m gpt-5 /path/to/project
```

Available models:

**Claude Models:**
- `claude-sonnet-4.5` (default) - Latest Claude model - 65,536 max tokens
- `claude-sonnet-4` - Claude Sonnet 4 - 65,536 max tokens
- `claude-3.7-sonnet` - Claude 3.7 Sonnet - 65,536 max tokens
- `claude-3.5-sonnet` - Claude 3.5 Sonnet - 8,192 max tokens

**OpenAI GPT Models (via Azure):**
- `gpt-5.2` - GPT-5.2 - 16,384 max tokens
- `gpt-5` - GPT-5 - 16,384 max tokens
- `o3` - OpenAI o3 - 100,000 max tokens
- `gpt-4o` - GPT-4o - 16,384 max tokens
- `gpt-4.1` - GPT-4.1 - 128,000 max tokens
- `o1` - OpenAI o1 - 100,000 max tokens

**Other Models:**
- `amazon-nova-pro` - Amazon Nova Pro - 32,768 max tokens
- `llama-3.3-70b` - Meta Llama 3.3 70B - 8,192 max tokens
- `llama-3.2-90b` - Meta Llama 3.2 90B - 8,192 max tokens

**Note:** Haiku models are not available on the MSK WebUI endpoint.

## Configuration

### LiteLLM Configuration (`litellm_config.yaml`)

The proxy is configured with:
- Model mappings to MSK WebUI models (Claude, GPT, Amazon Nova, Llama)
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
Claude CLI → LiteLLM Proxy (localhost:<dynamic-port>) → MSK Open WebUI (HTTPS) → AI Models (Claude, GPT, Nova, Llama)
```

The LiteLLM proxy:
1. Finds an available port and writes it to `.litellm_port`
2. Receives requests from Claude CLI in Anthropic API format
3. Translates them to OpenAI-compatible format
4. Forwards to MSK WebUI with your session token
5. Handles SSL verification bypass for internal MSK certificates
6. Returns responses in the format Claude CLI expects

The connection script:
1. Reads the port from `.litellm_port`
2. Configures Claude CLI to use that port
3. Launches Claude CLI with the selected model

## Troubleshooting

### Session Token Expired

If you get 401 errors, your session token may have expired. Get a new token from the browser and update `.auth.env`.

### SSL Certificate Errors

The proxy automatically handles SSL verification for the internal MSK server. If you still see SSL errors, make sure you're running the latest version of the proxy.

### Model Not Available

Some Claude models (like Haiku) are not available on MSK WebUI. If you try to use an unavailable model, you'll get an error. Use one of the supported models listed above instead.

### Port Already in Use

The proxy automatically finds the next available port starting from 22660. The port is saved to `.litellm_port` and automatically read by the connection scripts. No manual configuration is needed.

## Files

- `start_litellm_proxy.sh` - Starts the LiteLLM proxy server
- `start_litellm.py` - Python wrapper that patches SSL verification and finds available port
- `litellm_config.yaml` - LiteLLM proxy configuration
- `connect_claude.sh` - Wrapper to launch Claude CLI with proxy
- `setup_claude_env.sh` - Environment configuration for Claude CLI (reads `.litellm_port`)
- `.auth.env` - Your session token (create this, not in git)
- `.litellm_port` - Auto-generated port file (not in git)
- `requirements.txt` - Python dependencies

## Known Issues

### Claude Hangs on Trusting Working Directory

When running Claude CLI for the first time in a directory, it may hang when asking you to trust the working directory. This is a known issue with the CLI.

**Workaround:** Run Claude CLI without the custom endpoint first (using standard Claude), allow it to complete the trust prompt, then use the connector scripts afterward.

```bash
# First time in a new directory:
claude  # Run vanilla Claude, complete trust prompt
# Then use the connector:
./connect_claude.sh
```

### Running Out of Context

If Claude runs out of context during a long session, use the `/clear` command to start fresh:

```
/clear
```

This clears the conversation history while keeping your working directory and configuration.

## Security Notes

- Never commit `.auth.env` to git
- Session tokens expire periodically and need to be refreshed
- The proxy runs locally and only you can access it
- SSL verification is disabled only for the MSK internal server connection
