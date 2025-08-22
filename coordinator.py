# coordinator.py
import argparse, socket, threading, time, queue
from netutils import send_json, recv_lines, SafeSend, gen_id

# Diccionario global de workers conectados: worker_id -> WorkerConn
WORKERS = {}
WORKERS_LOCK = threading.Lock()

class WorkerConn:
    def __init__(self, sock, addr, worker_id):
        self.sock = sock
        self.addr = addr
        self.worker_id = worker_id
        self.sender = SafeSend(sock)
        self.alive = True

def handle_worker(conn: socket.socket, addr):
    buf = bytearray()
    worker_id = None
    try:
        # Espera mensaje de registro
        msgs = []
        while not msgs:
            msgs = recv_lines(conn, buf)
        reg = msgs[0]
        if reg.get("type") != "register":
            conn.close(); return
        worker_id = reg.get("worker_id") or gen_id("worker")
        wc = WorkerConn(conn, addr, worker_id)
        with WORKERS_LOCK:
            WORKERS[worker_id] = wc
        wc.sender.send({"type":"register_ok","worker_id":worker_id})
        # Loop de mensajes (pong, result, etc.)
        while True:
            msgs = recv_lines(conn, buf)
            if not msgs:
                break
            for m in msgs:
                t = m.get("type")
                if t == "pong":
                    # opcional: log/actualizar heartbeat
                    pass
                elif t == "result":
                    # El resultado se enruta vía task_manager (cola global)
                    TaskManager.deliver_result(m)
                # otros tipos según vayamos avanzando
    except Exception as e:
        pass
    finally:
        try: conn.close()
        except: pass
        if worker_id:
            with WORKERS_LOCK:
                WORKERS.pop(worker_id, None)

def worker_listener(host, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(100)
    print(f"[Coordinator] Esperando workers en {host}:{port}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_worker, args=(conn, addr), daemon=True).start()

# --- Gestión de tareas simples (una a la vez para el Paso 1/2)
class TaskManagerClass:
    def __init__(self):
        self.waiting = {}  # task_id -> {"pending": n, "accum": any, "op": str, "client": SafeSend}
        self.lock = threading.Lock()
    def submit_sum_range(self, client_sender: SafeSend, start: int, end: int, chunks: int):
        # Partir el rango entre workers disponibles
        with WORKERS_LOCK:
            worker_ids = list(WORKERS.keys())
        if not worker_ids:
            client_sender.send({"type":"job_error","error":"No hay workers conectados"})
            return
        # limitar chunks a #workers disponibles
        chunks = max(1, min(chunks, len(worker_ids)))
        # Crear sub-tareas
        total = end - start + 1
        step = total // chunks
        ranges = []
        s = start
        for i in range(chunks):
            e = end if i == chunks-1 else s + step - 1
            ranges.append((s, e))
            s = e + 1

        task_id = gen_id("task")
        with self.lock:
            self.waiting[task_id] = {"pending": chunks, "accum": 0, "op":"sum_range", "client": client_sender}

        # Enviar sub-tareas
        for i, (s0, e0) in enumerate(ranges):
            wid = worker_ids[i]
            wc = WORKERS.get(wid)
            if not wc: continue
            wc.sender.send({
                "type":"task",
                "task_id": task_id,
                "op":"sum_range",
                "payload":{"start": s0, "end": e0}
            })
        print(f"[Coordinator] Enviadas {chunks} sub-tareas para {task_id}")

    def submit_basic_operation(self, client_sender: SafeSend, operation: str, numbers: list, chunks: int):
        """Maneja operaciones básicas: sum, multiply, subtract, divide"""
        with WORKERS_LOCK:
            worker_ids = list(WORKERS.keys())
        if not worker_ids:
            client_sender.send({"type":"job_error","error":"No hay workers conectados"})
            return
        
        # Para operaciones básicas, dividir la lista de números entre workers
        chunks = max(1, min(chunks, len(worker_ids), len(numbers)))
        
        # Dividir números en sublistas
        numbers_per_chunk = len(numbers) // chunks
        sublists = []
        for i in range(chunks):
            start_idx = i * numbers_per_chunk
            if i == chunks - 1:  # último chunk toma todos los números restantes
                end_idx = len(numbers)
            else:
                end_idx = (i + 1) * numbers_per_chunk
            sublists.append(numbers[start_idx:end_idx])

        task_id = gen_id("task")
        
        # Valor inicial para la acumulación según operación
        if operation == "sum":
            initial_value = 0
        elif operation == "multiply":
            initial_value = 1
        elif operation == "subtract":
            initial_value = 0  # Se manejará especialmente
        elif operation == "divide":
            initial_value = 1  # Se manejará especialmente
        else:
            client_sender.send({"type":"job_error","error":f"Operación desconocida: {operation}"})
            return

        with self.lock:
            self.waiting[task_id] = {
                "pending": chunks, 
                "accum": initial_value, 
                "op": operation, 
                "client": client_sender,
                "results": [],  # Para operaciones que requieren orden
                "original_numbers": numbers  # Para subtract y divide
            }

        # Enviar sub-tareas
        for i, sublist in enumerate(sublists):
            if i < len(worker_ids):
                wid = worker_ids[i]
                wc = WORKERS.get(wid)
                if not wc: continue
                wc.sender.send({
                    "type":"task",
                    "task_id": task_id,
                    "op": operation,
                    "payload": {"numbers": sublist},
                    "chunk_index": i  # Para mantener orden en subtract/divide
                })
        print(f"[Coordinator] Enviadas {chunks} sub-tareas para {operation} ({task_id})")

    def deliver_result(self, msg):
        task_id = msg.get("task_id")
        part = msg.get("result")
        chunk_index = msg.get("chunk_index", 0)
        
        with self.lock:
            if task_id not in self.waiting:
                return
            entry = self.waiting[task_id]
            
            if entry["op"] == "sum_range":
                entry["accum"] += int(part)
            elif entry["op"] == "sum":
                entry["accum"] += float(part)
            elif entry["op"] == "multiply":
                entry["accum"] *= float(part)
            elif entry["op"] in ["subtract", "divide"]:
                # Para subtract y divide, necesitamos procesar en orden
                entry["results"].append({"index": chunk_index, "value": float(part)})
            
            entry["pending"] -= 1
            
            if entry["pending"] == 0:
                # Calcular resultado final
                final_result = entry["accum"]
                
                if entry["op"] == "subtract":
                    # Ordenar resultados por índice y procesar secuencialmente
                    entry["results"].sort(key=lambda x: x["index"])
                    if entry["results"]:
                        final_result = entry["results"][0]["value"]
                        for result in entry["results"][1:]:
                            final_result -= result["value"]
                
                elif entry["op"] == "divide":
                    # Ordenar resultados por índice y procesar secuencialmente
                    entry["results"].sort(key=lambda x: x["index"])
                    if entry["results"]:
                        final_result = entry["results"][0]["value"]
                        for result in entry["results"][1:]:
                            if result["value"] == 0:
                                entry["client"].send({"type":"job_error","task_id":task_id,"error":"División por cero"})
                                del self.waiting[task_id]
                                return
                            final_result /= result["value"]
                
                # Enviar resultado final al cliente y limpiar
                entry["client"].send({"type":"job_done","task_id":task_id,"result":final_result})
                del self.waiting[task_id]

TaskManager = TaskManagerClass()
TaskManager.deliver_result = TaskManager.deliver_result  # evitar linter

def client_handler(conn: socket.socket, addr):
    sender = SafeSend(conn)
    buf = bytearray()
    try:
        msgs = []
        # leer 1 línea JSON del cliente
        while not msgs:
            msgs = recv_lines(conn, buf)
        req = msgs[0]
        
        if req.get("type") == "job":
            op = req.get("op")
            chunks = int(req.get("chunks", 2))
            
            if op == "sum_range":
                p = req.get("payload") or {}
                start = int(p.get("start", 1))
                end = int(p.get("end", 100))
                TaskManager.submit_sum_range(sender, start, end, chunks)
            elif op in ["sum", "multiply", "subtract", "divide"]:
                p = req.get("payload") or {}
                numbers = p.get("numbers", [])
                if not numbers:
                    sender.send({"type":"job_error","error":"No se proporcionaron números"})
                    return
                TaskManager.submit_basic_operation(sender, op, numbers, chunks)
            else:
                sender.send({"type":"job_error","error":f"Operación desconocida: {op}"})
                return
            
            # esperar la respuesta final en el mismo socket (TaskManager la enviará)
            # mantener el socket abierto hasta que se cierre por el cliente
            while True:
                time.sleep(0.5)
        else:
            sender.send({"type":"job_error","error":"Solicitud desconocida"})
    except Exception:
        pass
    finally:
        try: conn.close()
        except: pass

def client_listener(host, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(100)
    print(f"[Coordinator] Esperando clientes en {host}:{port}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()

def pinger():
    # Hilo opcional que envía ping a workers cada 10s
    while True:
        time.sleep(10)
        with WORKERS_LOCK:
            for wc in WORKERS.values():
                try:
                    wc.sender.send({"type":"ping"})
                except Exception:
                    pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--worker-port", type=int, default=5001)
    ap.add_argument("--client-port", type=int, default=5002)
    args = ap.parse_args()
    threading.Thread(target=worker_listener, args=(args.bind, args.worker_port), daemon=True).start()
    threading.Thread(target=client_listener, args=(args.bind, args.client_port), daemon=True).start()
    threading.Thread(target=pinger, daemon=True).start()
    print("[Coordinator] Listo.")
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
