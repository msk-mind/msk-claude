# MSK AI Portal and Databricks for opencode, Claude Code and omp

⚠️ **All of this is API billing: you pay for every token. Be mindful of your token usage and costs.**

Use [opencode](https://opencode.ai), Claude Code or [omp](https://github.com/can1357/oh-my-pi) with the models on:

- **MSK's AI Portal** (Open WebUI at `https://chat.aicopilot.aws.mskcc.org`), through a LiteLLM proxy that runs on your machine
- **a Databricks workspace's Foundation Model APIs**, directly, with the profile you already use for the `databricks` CLI (see [Databricks](#databricks))

```bash
aiportal-opencode                     # opencode with Claude Sonnet 5.5 on the AI Portal
aiportal-opencode -m gpt-5.6-terra    # or any other model on the portal
aiportal-claude                       # Claude Code on the AI Portal
aiportal-omp                          # omp on the AI Portal
databricks-opencode                   # opencode with Claude Sonnet 5.5 on Databricks
databricks-claude                     # Claude Code on Databricks
databricks-omp                        # omp on Databricks
```

## Install

You need [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`) and opencode, Claude Code or omp.

```bash
uv tool install git+https://github.com/msk-mind/msk-claude
aiportal setup
```

For the AI Portal, `aiportal setup` asks for your session token and checks the whole setup. To get the token: log in to https://chat.aicopilot.aws.mskcc.org, open Developer Tools (F12; Cmd+Option+I on a Mac), go to the site's cookies (Chrome/Edge: Application tab; Firefox/Safari: Storage tab) and copy the value of the `token` cookie.

Tokens last 14 days. When yours runs out, the launch commands stop and ask you to run `aiportal token set` with a fresh one; they also warn you 2 days ahead.

**Update** with `uv tool upgrade aiportal`, which also brings the latest model list. **Uninstall** with `aiportal proxy stop && uv tool uninstall aiportal`; your token and state stay in `~/.config/aiportal` and `~/.local/state/aiportal` until you delete them.

### Coming from the Clone-Based Setup

If you used an earlier version from a clone of this repository, update the clone and run its installer once:

```bash
cd path/to/msk-claude && git pull && ./install.sh
```

It installs the package, replaces the old command links, stops the old proxy and moves your token and proxy key to their new place, so sessions you already have open keep working. It then lists the old files in the clone that you can delete. After that you don't need the clone.

## Usage

### opencode

```bash
aiportal-opencode                                  # default model, current directory
aiportal-opencode -m claude-opus-5.5               # a specific model
aiportal-opencode -m gpt-5.6-terra ~/project       # a model and a directory
aiportal-opencode --help                           # list models
```

Your global opencode config (`~/.config/opencode/opencode.json`) is never modified: the MSK provider is passed to opencode through `OPENCODE_CONFIG`, so your other providers and your default model stay as they are.

### Claude Code

```bash
aiportal-claude
aiportal-claude -m claude-opus-5.5 ~/project
eval "$(aiportal env)" && claude      # or set up the environment and run claude yourself
```

### omp

```bash
aiportal-omp
aiportal-omp -m gpt-5.6-terra ~/project
```

omp only reads custom providers from `~/.omp/agent/models.yml`, so `aiportal-omp` adds an `msk` provider there (or updates it), and leaves the rest of the file as is. The proxy key isn't written to the file: omp reads it from the `MSK_PROXY_KEY` environment variable. The provider points at the proxy of the machine you last launched `aiportal-omp` on, so if machines share your home directory, start omp with `aiportal-omp` rather than plain `omp`.

### Resuming Sessions

All three launchers can pick up an earlier session in the same directory:

| | opencode | Claude Code | omp |
|---|---|---|---|
| Continue the most recent session | `aiportal-opencode -c` | `aiportal-claude -c` | `aiportal-omp -c` |
| Resume a specific session | `aiportal-opencode -r <session-id>` | `aiportal-claude -r <session-id>` | `aiportal-omp -r <session-id>` |
| Choose from a list | `/sessions` inside opencode | `aiportal-claude -r` | `aiportal-omp -r` |
| Continue in a copy, leaving the original as is | add `--fork` | add `--fork` | not available |

With `aiportal-claude`, `-m` sets the model for the resumed conversation. Options and the directory can come in any order, e.g. `aiportal-opencode ~/project -c`.

### Managing the Proxy and Models

You don't need to start the proxy yourself. `aiportal-opencode`, `aiportal-claude` and `aiportal-omp` check your token, reuse this machine's proxy if it's running, and otherwise start one in the background. A proxy keeps running after you exit, and is restarted automatically (on the same port, so open sessions keep working) when your token, its key or aiportal itself changes. Use `aiportal` for everything else:

| Command | What it does |
|---|---|
| `aiportal setup` | First-time setup: token, moving over from the clone-based setup, checks |
| `aiportal doctor` | Check the whole setup and say what to fix |
| `aiportal token` | Show when your session token expires |
| `aiportal token set` | Save a new session token (checked with the portal first) |
| `aiportal proxy status` | Where the proxy is running and whether it answers |
| `aiportal proxy logs` | Follow this machine's proxy log |
| `aiportal proxy stop` | Stop this machine's background proxy |
| `aiportal proxy start` | Run the proxy in the foreground, to watch its output |
| `aiportal models` | List the configured models |
| `aiportal models sync` | Show models the portal has added or retired, compared with this version's list |
| `aiportal models sync --test` | Send a one-line prompt to every configured model |
| `aiportal env` | Print the environment for running `claude` yourself |

### Available Models

<!-- BEGIN MODEL LIST (generated by aiportal models sync) -->
**Claude Models:**
- `claude-sonnet-5.5` - Claude Sonnet 5.5 - 1,000,000 context / 128,000 max output
- `claude-sonnet-5` - Claude Sonnet 5 - 1,000,000 context / 128,000 max output
- `claude-sonnet-4.6` - Claude Sonnet 4.6 - 1,000,000 context / 64,000 max output
- `claude-sonnet-4.5` - Claude Sonnet 4.5 - 200,000 context / 64,000 max output
- `claude-opus-5.5` - Claude Opus 5.5 - 1,000,000 context / 128,000 max output
- `claude-opus-5` - Claude Opus 5 - 1,000,000 context / 128,000 max output
- `claude-opus-4.8` - Claude Opus 4.8 - 1,000,000 context / 128,000 max output
- `claude-opus-4.6` - Claude Opus 4.6 - 1,000,000 context / 128,000 max output

**OpenAI GPT Models (via Azure):**
- `gpt-5.6-terra` - GPT-5.6 Terra - 922,000 context / 128,000 max output
- `gpt-5.6-luna` - GPT-5.6 Luna - 922,000 context / 128,000 max output
- `gpt-5.5` - GPT-5.5 - 922,000 context / 128,000 max output
- `gpt-5.4` - GPT-5.4 - 922,000 context / 128,000 max output
- `gpt-5.2` - GPT-5.2 - 272,000 context / 128,000 max output
- `gpt-5` - GPT-5 - 272,000 context / 128,000 max output
- `o3` - o3 - 200,000 context / 100,000 max output
- `gpt-4.1` - GPT-4.1 - 1,047,576 context / 32,768 max output
- `o1` - o1 - 200,000 context / 100,000 max output

**Other Models:**
- `amazon-nova-pro` - Amazon Nova Pro - 300,000 context / 10,000 max output
- `llama-3.3-70b` - Llama 3.3 70B - 128,000 context / 8,192 max output
- `glm-5` - GLM-5 - 200,000 context / 128,000 max output
- `qwen3-vl-235b` - Qwen3 VL 235B A22B - 262,144 context / 32,768 max output
<!-- END MODEL LIST -->

The default is `claude-sonnet-5.5`. Haiku isn't available on the portal; Claude Code's Haiku requests go to Claude Sonnet 5.5.

## Databricks

`databricks-opencode`, `databricks-claude` and `databricks-omp` use the Foundation Model API endpoints of a Databricks workspace. They need no proxy and no `aiportal setup`: the workspace and token come from a profile in `~/.databrickscfg`, the one the `databricks` CLI uses (set one up with `databricks auth login`). Usage goes to the workspace's bill.

```bash
databricks-opencode                        # Claude Sonnet 5.5, profile DEFAULT
databricks-opencode -m gpt-6-sol ~/project # a model and a directory
databricks-claude -m claude-opus-5-5       # Claude Code (Claude models only)
databricks-omp -p dev                      # another profile, i.e. another workspace
databricks-opencode -c                     # continue the most recent session
```

The profile is `DEFAULT` unless you set `DATABRICKS_CONFIG_PROFILE` or pass `-p`. `-c`, `-r` and `--fork` work as for the AI Portal launchers ([Resuming Sessions](#resuming-sessions)); omp has no `--fork`.

| Model | Endpoint | Context / max output |
|---|---|---|
| `claude-sonnet-5-5` (default) | `databricks-claude-sonnet-5-5` | 1,000,000 / 128,000 |
| `claude-opus-5-5` | `databricks-claude-opus-5-5` | 1,000,000 / 128,000 |
| `claude-haiku-5-5` | `databricks-claude-haiku-5-5` | 1,000,000 / 128,000 |
| `gpt-6-sol` | `databricks-gpt-6-sol` | 922,000 / 128,000 |
| `gpt-5-6-terra` | `databricks-gpt-5-6-terra` | 922,000 / 128,000 |

The workspace offers more models (`databricks serving-endpoints list`), but these are the ones checked with tool calls in all three clients. Gemini and GLM endpoints don't work with opencode's tool calls.

How each client is set up:

- **opencode**: Claude goes through Databricks' Anthropic-format endpoint (`/serving-endpoints/anthropic`) and GPT through its OpenAI Responses endpoint (`/serving-endpoints/responses`). As with `aiportal-opencode`, the providers are passed in a separate config through `OPENCODE_CONFIG`, so your global opencode config isn't changed.
- **Claude Code**: `ANTHROPIC_BASE_URL` points at the Anthropic-format endpoint, and the `opus`, `sonnet` and `haiku` aliases map to the Databricks Claude models.
- **omp**: as with `aiportal-omp`, `databricks-omp` adds (or updates) two providers in `~/.omp/agent/models.yml`, `databricks-claude` and `databricks-openai`, and leaves the rest of the file as is. They replace the Claude Code beta flags omp sends, which Databricks rejects, and set the Claude models to adaptive thinking. After the first launch you can also pick these models in plain `omp`, as long as `DATABRICKS_FMAPI_TOKEN` is set.

The token is passed in the `DATABRICKS_FMAPI_TOKEN` environment variable, so it isn't written to any config file. A profile with a personal access token works for sessions of any length. With an OAuth profile, the launchers get a token from `databricks auth token`, which lasts about an hour; after that, quit and continue the session with `-c`.

## How It Works

```
opencode / Claude Code / omp ──> LiteLLM proxy (localhost) ──> MSK AI Portal (Open WebUI) ──> models
```

The proxy accepts OpenAI-format requests (opencode, omp) and Anthropic-format requests (Claude Code) and forwards them to the portal with your session token. Along the way it (`aiportal/callbacks.py`):

- removes parameters the portal doesn't support, and adds the `chat_id` field the portal requires
- puts a plain-language explanation in front of common errors, such as an expired token or a retired model

### Where Things Live

```
~/.config/aiportal/
  auth.env              your session token
~/.local/state/aiportal/
  master_key            secret the launchers use to authenticate to the proxy
  <hostname>/           one directory per machine
    server_info         where the proxy listens, and what it was started with
    proxy.pid, proxy.log, proxy.lock
    opencode.json       opencode config generated at launch (databricks-opencode.json for Databricks)
~/.omp/agent/models.yml omp's own config, where the omp launchers add their providers
```

Both are readable only by you, and follow `XDG_CONFIG_HOME` / `XDG_STATE_HOME` (or `AIPORTAL_CONFIG_DIR` / `AIPORTAL_STATE_DIR`). Proxy state is kept per machine, so machines that share your home directory (on a cluster, for example) don't interfere with each other.

### Sharing One Proxy Between Machines

By default the proxy only accepts connections from its own machine. To use one proxy from several machines that share your home directory, start it with `MSK_PROXY_BIND=0.0.0.0` (for example `MSK_PROXY_BIND=0.0.0.0 aiportal-opencode`). Launches on other machines that have no proxy of their own then find it and use it, with the same key. Traffic between machines is plain HTTP.

## Troubleshooting

**Start with `aiportal doctor`.** It checks the installation, your token, the model config, the proxy, the commands on your PATH and opencode / Claude Code, and prints the fix for anything wrong.

**Errors starting with `[MSK proxy]`** include the fix: run `aiportal token set` for a rejected token, or `uv tool upgrade aiportal` for a model the portal no longer offers.

**"No connected db" (HTTP 400).** The proxy rejected the session's key: LiteLLM reports a key it doesn't recognize this way. It happens when a session outlives the key it started with, for example after the key file was deleted and recreated. Quit and resume the session with `aiportal-opencode -c` or `aiportal-claude -c`. Ordinary proxy restarts don't cause this: the proxy comes back on the same port with the same key.

**The proxy won't start.** The launch command prints the end of the log. Run `aiportal proxy start` to see the full output in the foreground.

**Claude Code hangs on the "trust this folder" prompt** the first time you use it in a directory. Run plain `claude` there once to answer the prompt, then use `aiportal-claude`.

## Security

- Your token and the proxy key are readable only by you; the launchers tighten their permissions if they loosen.
- The proxy listens on localhost and requires the key, so other users can't spend your token through it.
- SSL verification is disabled only for the connection to the portal, which uses an internal certificate.

## Development

```bash
git clone https://github.com/msk-mind/msk-claude && cd msk-claude
uv run aiportal-opencode        # run from the source tree
uv run aiportal doctor
```

The code is in `src/aiportal/`: `launch.py` (the three AI Portal launchers), `omp.py` (omp's models.yml), `databricks.py` (the three Databricks launchers), `proxy.py` (starting and finding the proxy), `server.py` (runs LiteLLM), `callbacks.py` (request fixes and error hints), `auth.py`, `models.py`, `doctor.py`, `migrate.py` (`aiportal setup`) and `cli.py`. Dependencies are pinned to tested versions in `pyproject.toml`, because the proxy relies on LiteLLM internals; upgrade them deliberately and re-test with `uv run aiportal models sync --test`.

### Updating the Model List

`src/aiportal/litellm_config.yaml` is the single source of the model list; the launchers, the opencode config and the list above are generated from it. When the portal adds or retires models:

```bash
uv run aiportal models sync --apply   # update the config and this README
uv run aiportal models sync --test    # check every model answers
```

Then bump `version` in `pyproject.toml`, commit and open a PR. Once it's merged, everyone gets the new list with `uv tool upgrade aiportal`.
