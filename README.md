# Claude to Open WebUI Connector

This project connects Claude API to the Open WebUI instance at `https://chat.aicopilot.aws.mskcc.org`.

## Setup

1. **Install dependencies:**
   ```bash
   pip install requests anthropic
   ```

2. **Get your session token:**
   - Log in to https://chat.aicopilot.aws.mskcc.org in your browser
   - Open Developer Tools (F12)
   - Go to Application/Storage → Cookies
   - Copy the value of the `token` cookie
   
3. **Set session token:**
   ```bash
   export WEBUI_SESSION_TOKEN="your-token-here"
   ```

4. **Run the connector:**
   ```bash
   python claude_webui_connector.py
   ```

## Usage

### Basic Example

```python
from claude_webui_connector import WebUIConnector

# Initialize connector with session token
connector = WebUIConnector(
    base_url="https://chat.aicopilot.aws.mskcc.org",
    session_token="your-token-here"
)

# Get available models
models = connector.get_models()
print(models)

# Send a chat message
messages = [
    {"role": "user", "content": "Hello!"}
]
response = connector.chat_completion(messages, model="claude")
print(response)

# Stream responses
for chunk in connector.stream_chat_completion(messages, model="claude"):
    if 'choices' in chunk and len(chunk['choices']) > 0:
        delta = chunk['choices'][0].get('delta', {})
        if 'content' in delta:
            print(delta['content'], end='', flush=True)
```

## API Endpoints

The connector uses the following Open WebUI endpoints:

- **Get Models:** `GET /api/models`
- **Chat Completions:** `POST /api/chat/completions`
- **Streaming Chat:** `POST /api/chat/completions` (with `stream=true`)

## Configuration

- `base_url`: The base URL of your Open WebUI instance
- `session_token`: Your session token from browser cookies (can be set via `WEBUI_SESSION_TOKEN` environment variable)

## Notes

- The Open WebUI instance uses OpenAI-compatible API endpoints
- Authentication is done via session cookies (no API keys)
- Session tokens may expire - you'll need to refresh them by logging in again
- Model names may vary - use `get_models()` to see available models
