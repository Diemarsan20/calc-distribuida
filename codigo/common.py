"""Utilidades de mensajería para comunicación por sockets usando JSONL."""
import json
import socket

ENCODING = "utf-8"
EOL = "\n"

def send_json(sock: socket.socket, obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=False) + EOL
    sock.sendall(data.encode(ENCODING))

def recv_json(sock: socket.socket, bufsize: int = 65536) -> dict:
    chunks = []
    while True:
        b = sock.recv(1)
        if not b:
            break
        if b == b'\n':
            break
        chunks.append(b)
    if not chunks:
        return {}
    raw = b"".join(chunks).decode(ENCODING)
    return json.loads(raw)

def sum_squares(a: int, b: int) -> int:
    def f(n: int) -> int:
        return n * (n + 1) * (2 * n + 1) // 6
    if b < a:
        return 0
    return f(b) - f(a - 1)
