# worker.py
import argparse, socket, time
from netutils import send_json, recv_lines, SafeSend, gen_id

def op_sum_range(payload: dict) -> int:
    s = int(payload["start"]); e = int(payload["end"])
    # suma aritmética directa evita bucle: n*(a1+an)/2
    n = e - s + 1
    return n * (s + e) // 2

def op_sum(payload: dict) -> float:
    """Suma una lista de números"""
    numbers = payload.get("numbers", [])
    return sum(float(x) for x in numbers)

def op_multiply(payload: dict) -> float:
    """Multiplica una lista de números"""
    numbers = payload.get("numbers", [])
    if not numbers:
        return 0
    result = 1
    for x in numbers:
        result *= float(x)
    return result

def op_subtract(payload: dict) -> float:
    """Resta una lista de números (primer número menos el resto)"""
    numbers = payload.get("numbers", [])
    if not numbers:
        return 0
    if len(numbers) == 1:
        return float(numbers[0])
    result = float(numbers[0])
    for x in numbers[1:]:
        result -= float(x)
    return result

def op_divide(payload: dict) -> float:
    """Divide una lista de números (primer número dividido por el resto)"""
    numbers = payload.get("numbers", [])
    if not numbers:
        return 0
    if len(numbers) == 1:
        return float(numbers[0])
    result = float(numbers[0])
    for x in numbers[1:]:
        divisor = float(x)
        if divisor == 0:
            raise ValueError("División por cero")
        result /= divisor
    return result

OPS = {
    "sum_range": op_sum_range,
    "sum": op_sum,
    "multiply": op_multiply,
    "subtract": op_subtract,
    "divide": op_divide,
}

def run_worker(worker_id: str, coord_host: str, coord_port: int, reconnect_delay=3):
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((coord_host, coord_port))
            sender = SafeSend(sock)
            # registro
            sender.send({"type":"register","worker_id":worker_id,"capabilities":list(OPS.keys())})
            buf = bytearray()
            print(f"[{worker_id}] Conectado a {coord_host}:{coord_port}")
            while True:
                msgs = recv_lines(sock, buf)
                if not msgs:
                    break
                for m in msgs:
                    t = m.get("type")
                    if t == "ping":
                        sender.send({"type":"pong"})
                    elif t == "task":
                        task_id = m.get("task_id")
                        op = m.get("op")
                        payload = m.get("payload") or {}
                        chunk_index = m.get("chunk_index", 0)
                        if op in OPS:
                            try:
                                res = OPS[op](payload)
                                response = {"type":"result","task_id":task_id,"result":res}
                                if chunk_index is not None:
                                    response["chunk_index"] = chunk_index
                                sender.send(response)
                            except Exception as ex:
                                sender.send({"type":"result","task_id":task_id,"error":str(ex)})
                        else:
                            sender.send({"type":"result","task_id":task_id,"error":"op no soportada"})
        except (ConnectionRefusedError, OSError):
            print(f"[{worker_id}] No se pudo conectar. Reintentando en {reconnect_delay}s...")
            time.sleep(reconnect_delay)
        except Exception as e:
            print(f"[{worker_id}] Error: {e}")
            time.sleep(reconnect_delay)
        finally:
            try: sock.close()
            except: pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=gen_id("worker"))
    ap.add_argument("--coord-host", required=True)
    ap.add_argument("--coord-port", type=int, default=5001)
    args = ap.parse_args()
    run_worker(args.id, args.coord_host, args.coord_port)

if __name__ == "__main__":
    main()
