with open("backend/app/server.py", "r") as f:
    server_content = f.read()

# Force close_connection to True at the end of _set_headers
old_set_headers = """    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()"""

new_set_headers = """    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True"""

server_content = server_content.replace(old_set_headers, new_set_headers)

with open("backend/app/server.py", "w") as f:
    f.write(server_content)
