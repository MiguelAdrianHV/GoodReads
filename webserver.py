from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
from urllib.parse import parse_qs
from html.parser import HTMLParser
import re
import redis
import uuid
import os

r = redis.Redis(host='localhost', port=6379, db=0)

# Código basado en:
# https://realpython.com/python-http-server/
# https://docs.python.org/3/library/http.server.html
# https://docs.python.org/3/library/http.cookies.html

class MyHTMLParser(HTMLParser):
    def __init__(self, tag_id):
        super().__init__()
        self.tag_id = tag_id
        self.in_target_tag = False
        self.data = ""

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            for name, value in attrs:
                if name == "id" and value == self.tag_id:
                    self.in_target_tag = True

    def handle_data(self, data):
        if self.in_target_tag:
            self.data += data

    def handle_endtag(self, tag):
        if self.in_target_tag and tag == "p":
            self.in_target_tag = False

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
    
    def set_book_cookie(self, session_id, max_age=10):
        c = SimpleCookie()
        c["session"] = session_id
        c["session"]["max-age"] = max_age
        self.send_header('Set-Cookie', c.output(header=''))

    def get_book_session(self):
        c = self.cookies
        if not c:
            print("No cookie")
            c = SimpleCookie()
            c["session"] = uuid.uuid4()
        else:
            print("Cookie found")
        return c.get("session").value

    def do_GET(self):
        method = self.get_method(self.url.path)
        if method:
            method_name, dict_params = method
            method = getattr(self, method_name)
            method(**dict_params)
            return
        else:
            self.send_error(404, "Not Found")

    def get_book_recomendation(self, session_id, book_id):
        r.rpush(session_id, book_id)
        books = r.lrange(session_id, 0, 5)
        print(session_id, books)
        all_books = [str(i+1) for i in range(4)]
        new = [b for b in all_books if b not in
               [vb.decode() for vb in books]]
        if new:
            return new[0]

    def get_book(self, book_id):
        session_id = self.get_book_session()
        book_recomendation = self.get_book_recomendation(session_id, book_id)
        book_page = r.get(book_id)
        if book_page:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.set_book_cookie(session_id)
            self.end_headers()
            response = f"""
    <h1>La Biblioteca</h1>       
        
    <a href="/">
        <button>
            Volver
        </button>
    </a>
            {book_page.decode()}
        <p>  <strong> Ruta: </strong> {self.path}            </p>
        <p>  <strong> URL: </strong> {self.url}              </p>
        <p>  <strong> Headers: </strong> {self.headers}      </p>
        <p>  <strong> Token: </strong> {session_id}      </p>
        <p>  <strong> Recomendación: </strong> {book_recomendation}      </p>
"""
            self.wfile.write(response.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def get_index(self):
        session_id = self.get_book_session()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.set_book_cookie(session_id)
        self.end_headers()
        with open('html/index.html') as f:
            response = f.read()
        self.wfile.write(response.encode("utf-8"))

    def get_search(self):
        session_id = self.get_book_session()
        book_results = self.book_search(self.url.query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.set_book_cookie(session_id)
        self.end_headers()
        with open('html/search.html') as f:
            response = f"""
            {f.read()}
            <p> {book_results} </p>
            """
        self.wfile.write(response.encode("utf-8"))
    
    def book_search(self, query):
        query_params = parse_qs(query)
        name = query_params.get('search_name', [''])[0]
        autor = query_params.get('search_autor', [''])[0]
        description = query_params.get('search_description', [''])[0]
        book_list = []
        book_final_string = ""
    
        for book in range(1,5):
            book_page = r.get(book)
            book_string = book_page.decode()
            book_flag = True
    
            if name:
                name_value = self.single_search("nombre_libro", book_string)
                if not name in name_value:
                    book_flag = False

            if autor:
                autor_value = self.single_search("nombre_autor", book_string)
                if not autor in autor_value:
                    book_flag = False

            if description:
                description_value = self.single_search("description", book_string)
                if not description in description_value:
                    book_flag = False
            
            if not name and not autor and not description:
                book_flag = False

            if book_flag:
                book_final_string += book_string

        return book_final_string
    
    def single_search(self, htmlid, book_string):
        parser = MyHTMLParser(htmlid)
        parser.feed(book_string)
        nombre_value = parser.data.strip()
        return nombre_value

    def get_method(self, path):
        for pattern, method in mapping:
            match = re.match(pattern, path)
            if match:
                return (method, match.groupdict())
    
def load_folder(path):
    files = os.listdir(path)
    print(files)
    for file in files:
        match = re.match(r'^book(\d+).html$', file)
        if match:
            with open(path + file) as f:
                html = f.read()
                r.set(match.group(1), html)
            print(match.group(0), match.group(1))


load_folder('html/books/')


mapping = [
            (r'^/books/(?P<book_id>\d+)$', 'get_book'),
            (r'^/$', 'get_index'),
            (r'^/search$', 'get_search')
            ]

if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 80), WebRequestHandler)
    server.serve_forever()
