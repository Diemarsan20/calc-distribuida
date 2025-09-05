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
    """
    Envía una solicitud a un worker específico y espera la respuesta.
    Maneja timeouts y errores de conexión.
    """
    host, port_str = addr.split(":")
    port = int(port_str)
    print(f"[COORDINATOR] Enviando solicitud a worker {addr}")
    print(f"[COORDINATOR] Payload: {payload}")
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        print(f"[COORDINATOR] Conectado a {addr}")
        send_json(s, payload)
        response = recv_json(s)
        print(f"[COORDINATOR] Respuesta recibida de {addr}: {response}")
        return response
    except Exception as e:
        print(f"[COORDINATOR] ERROR al conectar con {addr}: {e}")
        return None
    finally:
        s.close()

def try_workers(workers, payload):
    """
    Intenta ejecutar la tarea en los workers de la lista, uno por uno.
    Retorna la primera respuesta exitosa o None si todos fallan.
    """
    print(f"[COORDINATOR] Intentando con {len(workers)} workers: {workers}")
    
    for i, w in enumerate(workers):
        print(f"[COORDINATOR] Intento {i+1}/{len(workers)} con worker {w}")
        try:
            r = ask_worker(w, payload)
            if r:
                if r.get("ok"):
                    print(f"[COORDINATOR] ✅ Éxito con worker {w}")
                    # Agregar información del worker que procesó la tarea
                    r["_worker_used"] = w
                    return r
                else:
                    # Worker respondió con un error (ej: división por cero)
                    print(f"[COORDINATOR] ⚠️ Worker {w} reportó error: {r.get('error', 'Error desconocido')}")
                    r["_worker_used"] = w
                    return r  # Retornar el error inmediatamente
            else:
                print(f"[COORDINATOR] ❌ Worker {w} no respondió")
        except Exception as e:
            print(f"[COORDINATOR] ❌ Excepción con worker {w}: {e}")
            continue
    
    print(f"[COORDINATOR] ❌ Todos los workers fallaron")
    return None

def split_range(n: int, parts: int):
    """
    Divide el rango 1..n en 'parts' subrangos lo más equilibrados posible.
    Retorna lista de tuplas (a,b).
    """
    print(f"[COORDINATOR] Dividiendo rango 1..{n} en {parts} partes")
    
    size = n // parts
    extra = n % parts
    ranges = []
    start = 1
    
    for i in range(parts):
        end = start + size - 1
        if i < extra:
            end += 1
        ranges.append((start, end))
        print(f"[COORDINATOR] Parte {i+1}: rango {start}..{end}")
        start = end + 1
    
    print(f"[COORDINATOR] Rangos generados: {ranges}")
    return ranges

def handle_client(conn: socket.socket, workers: list, rr_state: dict):
    """
    Maneja una conexión de cliente.
    Procesa la solicitud y coordina con los workers.
    """
    print(f"[COORDINATOR] Nueva conexión de cliente")
    
    try:
        # Recibir solicitud del cliente
        print(f"[COORDINATOR] Esperando solicitud del cliente...")
        req = recv_json(conn)
        if not req:
            print(f"[COORDINATOR] No se recibió solicitud válida")
            return
        
        op = req.get("op")
        print(f"[COORDINATOR] Operación solicitada: {op}")
        print(f"[COORDINATOR] Datos recibidos: {req}")

        # --- operaciones básicas (round-robin) ---
        if op in ("add", "sub", "mul", "div"):
            print(f"[COORDINATOR] Procesando operación básica: {op}")
            
            # Seleccionar worker usando round-robin
            idx = rr_state["counter"] % len(workers)
            rr_state["counter"] += 1
            selected_worker = workers[idx]
            print(f"[COORDINATOR] Worker seleccionado (round-robin): {selected_worker}")
            
            payload = {"op": op, "a": req.get("a"), "b": req.get("b")}
            r = try_workers(workers[idx:] + workers[:idx], payload)
            
            if r:
                if r.get("ok"):
                    print(f"[COORDINATOR] ✅ Operación completada exitosamente")
                    send_json(conn, r)
                else:
                    print(f"[COORDINATOR] ⚠️ Operación falló: {r.get('error', 'Error desconocido')}")
                    # Enviar error genérico al cliente para operaciones básicas
                    if "División por cero" in r.get('error', ''):
                        send_json(conn, r)  # Mantener error específico para división por cero
                    else:
                        send_json(conn, {"ok": False, "error": "sistema_temporalmente_ocupado"})
            else:
                print(f"[COORDINATOR] ❌ Ningún worker disponible para operación básica")
                send_json(conn, {"ok": False, "error": "sistema_temporalmente_ocupado"})
            return

        # --- sumatoria de cuadrados (distribuida) ---
        if op == "sum_squares":
            n = int(req.get("n"))
            print(f"[COORDINATOR] Procesando sumatoria de cuadrados para n={n}")
            
            # Dividir el trabajo entre workers disponibles
            ranges = split_range(n, len(workers))
            results = []
            total = 0
            available_workers = workers.copy()  # Lista de workers disponibles
            worker_index = 0  # Para distribución round-robin
            
            print(f"[COORDINATOR] Distribuyendo trabajo entre {len(workers)} workers")
            print(f"[COORDINATOR] Workers disponibles: {available_workers}")
            
            for i, (a, b) in enumerate(ranges):
                print(f"[COORDINATOR] Procesando rango {a}..{b}")
                payload = {"op": "sum_squares", "a": a, "b": b}
                
                # Distribuir trabajo usando round-robin entre workers disponibles
                # Intentar primero con el worker asignado, luego con otros si falla
                assigned_worker = available_workers[worker_index % len(available_workers)]
                worker_index += 1
                
                print(f"[COORDINATOR] Asignando rango {a}..{b} a worker {assigned_worker}")
                
                # Crear lista de workers para retry: worker asignado primero, luego los demás
                retry_workers = [assigned_worker] + [w for w in available_workers if w != assigned_worker]
                r = try_workers(retry_workers, payload)
                
                if not r:
                    print(f"[COORDINATOR] ❌ No se pudo completar la tarea (todos los workers caídos)")
                    send_json(conn, {"ok": False, "error": "sistema_temporalmente_ocupado"})
                    return
                
                result_value = int(r["result"])
                worker_used = r.get("_worker_used", assigned_worker)
                # Agregar información del worker que procesó este rango
                results.append({
                    "a": r.get("a"), 
                    "b": r.get("b"), 
                    "result": result_value,
                    "worker": worker_used
                })
                total += result_value
                print(f"[COORDINATOR] Rango {a}..{b} completado por {worker_used}: {result_value}")
            
            print(f"[COORDINATOR] ✅ Sumatoria completada. Total: {total}")
            print(f"[COORDINATOR] 📊 Distribución del trabajo:")
            for i, part in enumerate(results, 1):
                worker_addr = part.get('worker', f'Worker {i}')
                print(f"[COORDINATOR]    {worker_addr}: rango {part['a']}..{part['b']} = {part['result']}")
            send_json(conn, {"ok": True, "result": total, "parts": results})
            return

        # --- operación no soportada ---
        error_msg = f"operación no soportada: {op}"
        print(f"[COORDINATOR] ❌ {error_msg}")
        send_json(conn, {"ok": False, "error": error_msg})

    except Exception as e:
        error_msg = str(e)
        print(f"[COORDINATOR] ERROR durante procesamiento: {error_msg}")
        try:
            send_json(conn, {"ok": False, "error": error_msg})
        except Exception:
            print(f"[COORDINATOR] ERROR: No se pudo enviar respuesta de error")
            pass
    finally:
        print(f"[COORDINATOR] Cerrando conexión con cliente")
        conn.close()

def main():
    """
    Función principal del coordinador.
    Configura el servidor y espera conexiones de clientes.
    """
    parser = argparse.ArgumentParser(description="Coordinador del sistema distribuido")
    parser.add_argument("--host", default="127.0.0.1", help="Dirección IP para escuchar")
    parser.add_argument("--port", type=int, default=5000, help="Puerto para escuchar")
    parser.add_argument("--workers", nargs="+", required=True, help="Lista de workers host:port")
    args = parser.parse_args()

    print(f"[COORDINATOR] Iniciando coordinador en {args.host}:{args.port}")
    print(f"[COORDINATOR] Workers configurados: {args.workers}")
    print(f"[COORDINATOR] Esperando conexiones de clientes...")
    
    # Configurar el socket del servidor
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(5)

    print(f"[COORDINATOR] ✅ Coordinador listo y escuchando en {args.host}:{args.port}")
    print(f"[COORDINATOR] Workers disponibles: {args.workers}")
    print(f"[COORDINATOR] Presiona Ctrl+C para detener el coordinador")

    # Estado para round-robin de operaciones básicas
    rr_state = {"counter": 0}

    try:
        while True:
            print(f"[COORDINATOR] Esperando nueva conexión de cliente...")
            conn, addr = srv.accept()
            print(f"[COORDINATOR] Cliente conectado desde {addr}")
            handle_client(conn, args.workers, rr_state)
    except KeyboardInterrupt:
        print(f"\n[COORDINATOR] Deteniendo coordinador...")
    finally:
        print(f"[COORDINATOR] Cerrando servidor...")
        srv.close()
        print(f"[COORDINATOR] Coordinador detenido")

if __name__ == "__main__":
    main()
