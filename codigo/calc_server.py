"""
calc_server.py - Servidor principal / coordinador de cálculo con tolerancia a fallos.
Acepta peticiones de clientes y distribuye el trabajo a N workers.
Si un worker falla, reintenta con otro disponible.
Uso:
  python calc_server.py --host 127.0.0.1 --port 5000 --workers 127.0.0.1:6001 127.0.0.1:6002 127.0.0.1:6003
"""
import argparse
import socket
from common import send_json, recv_json

def ask_worker(addr: str, payload: dict, timeout=5.0) -> dict:
    host, port_str = addr.split(":")
    port = int(port_str)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        send_json(s, payload)
        return recv_json(s)
    finally:
        s.close()

def try_workers(workers, payload):
    """
    Intenta ejecutar la tarea en los workers de la lista, uno por uno.
    Retorna la primera respuesta exitosa o None si todos fallan.
    """
    for w in workers:
        try:
            r = ask_worker(w, payload)
            if r and r.get("ok"):
                return r
        except Exception:
            continue
    return None

def split_range(n: int, parts: int):
    """
    Divide el rango 1..n en 'parts' subrangos lo más equilibrados posible.
    Retorna lista de tuplas (a,b).
    """
    size = n // parts
    extra = n % parts
    ranges = []
    start = 1
    for i in range(parts):
        end = start + size - 1
        if i < extra:
            end += 1
        ranges.append((start, end))
        start = end + 1
    return ranges

def handle_client(conn: socket.socket, workers: list, rr_state: dict):
    try:
        req = recv_json(conn)
        if not req:
            return
        op = req.get("op")

        # --- operaciones básicas ---
        if op in ("add", "sub", "mul", "div"):
            # round-robin en los workers
            idx = rr_state["counter"] % len(workers)
            rr_state["counter"] += 1
            payload = {"op": op, "a": req.get("a"), "b": req.get("b")}
            r = try_workers(workers[idx:] + workers[:idx], payload)
            if r:
                send_json(conn, r)
            else:
                send_json(conn, {"ok": False, "error": "ningún worker disponible"})
            return

        # --- sumatoria de cuadrados ---
        if op == "sum_squares":
            n = int(req.get("n"))
            ranges = split_range(n, len(workers))
            results = []
            total = 0
            for (a, b), w in zip(ranges, workers):
                payload = {"op": "sum_squares", "a": a, "b": b}
                r = try_workers([w] + workers, payload)
                if not r:
                    send_json(conn, {"ok": False, "error": "no se pudo completar la tarea (workers caídos)"})
                    return
                results.append({"a": r.get("a"), "b": r.get("b"), "result": r.get("result")})
                total += int(r["result"])
            send_json(conn, {"ok": True, "result": total, "parts": results})
            return

        # --- operación no soportada ---
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
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--workers", nargs="+", required=True, help="Lista de workers host:port")
    args = parser.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(5)

    print(f"[calc-server] listening on {args.host}:{args.port}")
    print(f"Workers: {args.workers}")

    rr_state = {"counter": 0}  # para round-robin de operaciones básicas

    try:
        while True:
            conn, addr = srv.accept()
            handle_client(conn, args.workers, rr_state)
    finally:
        srv.close()

if __name__ == "__main__":
    main()
