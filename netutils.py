# netutils.py
import json, socket, threading, uuid

DELIM = b"\n"

def send_json(sock: socket.socket, obj: dict):
    data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
    sock.sendall(data)

def recv_lines(sock: socket.socket, buffer: bytearray):
    # Devuelve lista de objetos JSON completos leídos; mantiene el buffer.
    chunks = []
    while True:
        try:
            data = sock.recv(4096)
        except ConnectionResetError:
            raise
        if not data:
            break
        buffer += data
        while True:
            idx = buffer.find(DELIM)
            if idx == -1:
                break
            line = buffer[:idx]
            del buffer[:idx+1]
            if not line:
                continue
            chunks.append(json.loads(line.decode("utf-8")))
    return chunks

def gen_id(prefix="id"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

class SafeSend:
    # Enviar por socket desde varios hilos sin pisarse
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.lock = threading.Lock()
    def send(self, obj: dict):
        with self.lock:
            send_json(self.sock, obj)
