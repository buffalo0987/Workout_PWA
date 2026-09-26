with open("backend/app/server.py", "r") as f:
    server_content = f.read()

import re

post_test_conn = """
            if path == "/api/settings/test-connection":
                results = test_service_connections(body)
                self._send_json(200, results)
                return
"""

if 'path == "/api/settings/test-connection"' not in server_content.split('def do_POST(self):')[1]:
    server_content = server_content.replace('if path == "/api/coaching/chat":', post_test_conn.lstrip() + '\n            if path == "/api/coaching/chat":')
    with open("backend/app/server.py", "w") as f:
        f.write(server_content)
