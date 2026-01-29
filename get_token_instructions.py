#!/usr/bin/env python3
"""
Instructions for getting the session token from the browser
"""

print("""
==================================================================
HOW TO GET YOUR SESSION TOKEN
==================================================================

1. Open your browser and go to:
   https://chat.aicopilot.aws.mskcc.org

2. Log in with your MSK credentials

3. Open Developer Tools:
   - Chrome/Edge: Press F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)
   - Firefox: Press F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)
   - Safari: Enable Developer menu first, then press Cmd+Option+I

4. Navigate to cookies:
   - Chrome/Edge: Application tab → Cookies → https://chat.aicopilot.aws.mskcc.org
   - Firefox: Storage tab → Cookies → https://chat.aicopilot.aws.mskcc.org
   - Safari: Storage tab → Cookies → chat.aicopilot.aws.mskcc.org

5. Find the cookie named "token" and copy its value

6. Set the environment variable:
   export WEBUI_SESSION_TOKEN="paste-your-token-here"

7. Run the connector:
   python claude_webui_connector.py

==================================================================
NOTE: Session tokens expire after some time. If you get 401 errors,
you'll need to get a fresh token by logging in again.
==================================================================
""")
