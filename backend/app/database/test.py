import socket, ssl, certifi

host = "ac-cakypqg-shard-00-00.7kcgihd.mongodb.net"
port = 27017

ctx = ssl.create_default_context(cafile=certifi.where())

with socket.create_connection((host, port)) as sock:
    with ctx.wrap_socket(sock, server_hostname=host) as ssock:
        print("TLS handshake succeeded!")

