with open("backend/app/server.py", "r") as f:
    server_content = f.read()

import re

old_send_json = """    def _send_json(self, status, payload):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        except Exception as e:
            logger.error(f"Error parsing JSON request: {e}")"""

new_send_json = """    def _send_json(self, status, payload):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            self.close_connection = True
        except Exception as e:
            logger.error(f"Error parsing JSON request: {e}")"""

server_content = server_content.replace(old_send_json, new_send_json)

with open("backend/app/server.py", "w") as f:
    f.write(server_content)
