import unittest
import socket
from TCPProxy import receive_from, request_handler, response_handler

class TestTCPProxy(unittest.TestCase):

    def test_receive_from(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("localhost", 9999))
        server.listen(1)
        client = socket.create_connection(("localhost", 9999))
        conn, _ = server.accept()
        client.send(b"Test data")
        data = receive_from(conn)
        self.assertEqual(data, b"Test data")
        server.close()
        client.close()

    def test_request_handler(self):
        request = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        modified_request = request_handler(request)
        self.assertIn(b"POST", modified_request)

    def test_response_handler(self):
        response = b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n"
        modified_response = response_handler(response)
        self.assertIn(b"<h1>Custom 404 Page</h1>", modified_response)

if __name__ == '__main__':
    unittest.main()
