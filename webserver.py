from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
import re
import redis
import uuid

r = redis.Redis(host='localhost', port=6379, db=0)

# Código basado en:
# https://realpython.com/python-http-server/
# https://docs.python.org/3/library/http.server.html
# https://docs.python.org/3/library/http.cookies.html


class WebRequestHandler(BaseHTTPRequestHandler):
    @cached_property
    def url(self):
        return urlparse(self.path)

    @cached_property
    def query_data(self):
        return dict(parse_qsl(self.url.query))

    @cached_property
    def post_data(self):
        content_length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(content_length)

    @cached_property
    def form_data(self):
        return dict(parse_qsl(self.post_data.decode("utf-8")))

    @cached_property
    def cookies(self):
        return SimpleCookie(self.headers.get("Cookie"))
    

    def do_GET(self):
        method = self.get_method(self.url.path)
        if method:
            method_name, dict_params = method
            method = getattr(self, method_name)
            method(**dict_params)
            return
        else:
            self.send_error(404, "Not Found")


    def get_book(self, book_id):
        book_page = r.get(book_id)
        if book_page:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            response = f"""
            {book_page.decode()}
        <p>  Ruta: {self.path}            </p>
        <p>  URL: {self.url}              </p>
        <p>  HEADERS: {self.headers}      </p>
"""
            self.wfile.write(response.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def get_index(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        with open('html/index.html') as f:
            response = f.read()
        self.wfile.write(response.encode("utf-8"))
    
    def get_method(self, path):
        for pattern, method in mapping:
            match = re.match(pattern, path)
            if match:
                return (method, match.groupdict())


mapping = [
            (r'^/books/(?P<book_id>\d+)$', 'get_book'),
            (r'^/$', 'get_index')
            ]

if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 80), WebRequestHandler)
    server.serve_forever()
