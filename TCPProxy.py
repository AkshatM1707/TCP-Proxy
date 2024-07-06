#!/usr/bin/env python3
import sys
import socket
import threading
import logging
import argparse
import json
import ssl

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cache for caching responses
cache = {}

def server_loop(local_host, local_port, remote_host, remote_port, receive_first):
    server = create_ssl_socket()

    try:
        server.bind((local_host, local_port))
    except Exception as e:
        logging.error(f"Failed to listen on {local_host}:{local_port}")
        logging.error(f"Check for other listening sockets or correct permissions\nError: {e}")
        sys.exit(0)

    logging.info(f"Listening on {local_host}:{local_port}")

    server.listen(5)
    while True:
        client_socket, addr = server.accept()
        logging.info(f"Received incoming connection from {addr[0]}:{addr[1]}")

        proxy_thread = threading.Thread(
            target=proxy_handler,
            args=(client_socket, remote_host, remote_port, receive_first)
        )
        proxy_thread.start()

def create_ssl_socket():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket = context.wrap_socket(server_socket, server_side=True)
    return server_socket

def parse_args():
    parser = argparse.ArgumentParser(description="TCP Proxy Tool")
    parser.add_argument("localhost", help="Local host to bind to")
    parser.add_argument("localport", type=int, help="Local port to bind to")
    parser.add_argument("remotehost", help="Remote host to forward to")
    parser.add_argument("remoteport", type=int, help="Remote port to forward to")
    parser.add_argument("receive_first", type=str, help="Receive data from remote first (True/False)")
    parser.add_argument("--config", help="Path to configuration file", default=None)
    return parser.parse_args()

def load_config(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def main():
    args = parse_args()

    if args.config:
        config = load_config(args.config)
        local_host = config['local_host']
        local_port = config['local_port']
        remote_host = config['remote_host']
        remote_port = config['remote_port']
        receive_first = config['receive_first']
    else:
        local_host = args.localhost
        local_port = int(args.localport)
        remote_host = args.remotehost
        remote_port = int(args.remoteport)
        receive_first = args.receive_first.lower() == 'true'

    server_loop(local_host, local_port, remote_host, remote_port, receive_first)

def proxy_handler(client_socket, remote_host, remote_port, receive_first):
    remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    remote_socket.connect((remote_host, remote_port))

    if receive_first:
        remote_buffer = receive_from(remote_socket)
        hexdump(remote_buffer)
        remote_buffer = response_handler(remote_buffer)
        if len(remote_buffer):
            logging.info(f"Sending {len(remote_buffer)} bytes to localhost.")
            client_socket.send(remote_buffer)

    while True:
        local_buffer = receive_from(client_socket)
        if len(local_buffer):
            logging.info(f"Received {len(local_buffer)} bytes from localhost.")
            hexdump(local_buffer)
            local_buffer = request_handler(local_buffer)
            remote_socket.send(local_buffer)
            logging.info("Sent to remote.")

        remote_buffer = receive_from(remote_socket)
        if len(remote_buffer):
            logging.info(f"Received {len(remote_buffer)} bytes from remote.")
            hexdump(remote_buffer)
            remote_buffer = response_handler(remote_buffer)
            client_socket.send(remote_buffer)
            logging.info("Sent to localhost")

        if not len(local_buffer) and not len(remote_buffer):
            client_socket.close()
            remote_socket.close()
            logging.info("No more data. Closing connections.")
            break

def hexdump(src, length=16):
    result = []
    digits = 4 if isinstance(src, str) else 2
    for i in range(0, len(src), length):
        s = src[i:i + length]
        hexa = ' '.join([f"{ord(x):0{digits}X}" for x in s])
        text = ''.join([x if 0x20 <= ord(x) < 0x7F else '.' for x in s])
        result.append(f"{i:04X} {hexa:<{length * (digits + 1)}} {text}")
    print('\n'.join(result))

def receive_from(connection):
    buffer = b""
    connection.settimeout(2)
    try:
        while True:
            data = connection.recv(4096)
            if not data:
                break
            buffer += data
    except socket.timeout:
        logging.warning("Connection timed out.")
    except Exception as e:
        logging.error(f"Error receiving data: {e}")
    return buffer

def request_handler(buffer):
    # Caching logic
    cache_key = hash(buffer)
    if cache_key in cache:
        logging.info("Cache hit, returning cached response")
        return cache[cache_key]
    if b"GET" in buffer:
        buffer = buffer.replace(b"GET", b"POST")
    return buffer

def response_handler(buffer):
    # Caching logic
    cache_key = hash(buffer)
    cache[cache_key] = buffer
    if b"404 Not Found" in buffer:
        buffer = b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n"
        buffer += b"<html><body><h1>Custom 404 Page</h1></body></html>"
    return buffer

if __name__ == "__main__":
    main()
