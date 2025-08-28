"""
worker.py - Servidor de operación (trabajador)
Escucha en HOST:PORT y atiende solicitudes del servidor de cálculo.
Uso:
  python worker.py --host 127.0.0.1 --port 6001
"""
import argparse
import socket
from common import send_json, recv_json, sum_squares

def handle_connection(conn: socket.socket, addr):
    try:
        req = recv_json(conn)
        if not req:
            return
        op = req.get("op")

        if op == "sum_squares":
            a = int(req.get("a"))
            b = int(req.get("b"))
            result = sum_squares(a, b)
            send_json(conn, {"ok": True, "result": result, "a": a, "b": b, "op": op})

        elif op in ("add", "sub", "mul", "div"):
            a = float(req.get("a"))
            b = float(req.get("b"))

            if op == "add":
                result = a + b
            elif op == "sub":
                result = a - b
            elif op == "mul":
                result = a * b
            elif op == "div":
                if b == 0:
                    raise ValueError("División por cero")
                result = a / b

            send_json(conn, {"ok": True, "result": result, "a": a, "b": b, "op": op})

        else:
            send_json(conn, {"ok": False, "error": f"operación no soportada: {op}"})

    except Exception as e:
        try:
            send_json(conn, {"ok": False, "error": str(e)})
        except Exception:
            pass
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6001)
    args = parser.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(5)
    print(f"[worker] listening on {args.host}:{args.port}")
    try:
        while True:
            conn, addr = srv.accept()
            handle_connection(conn, addr)
    finally:
        srv.close()

if __name__ == "__main__":
    main()
