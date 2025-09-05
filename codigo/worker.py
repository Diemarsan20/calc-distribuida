"""
worker.py - Servidor de operación (trabajador)
Escucha en HOST:PORT y atiende solicitudes del servidor de cálculo.
Uso:
  python worker.py --host 127.0.0.1 --port 6001
"""
import argparse
import socket
from common import send_json, recv_json, sum_squares

def handle_connection(conn: socket.socket, addr, operation_count):
    """
    Maneja una conexión entrante del coordinador.
    Procesa la solicitud y envía la respuesta.
    """
    print(f"[WORKER] Nueva conexión desde {addr}")
    
    try:
        # Recibir la solicitud del coordinador
        print(f"[WORKER] Esperando solicitud...")
        req = recv_json(conn)
        if not req:
            print(f"[WORKER] No se recibió solicitud válida")
            return operation_count
        
        op = req.get("op")
        print(f"[WORKER] Operación solicitada: {op}")
        print(f"[WORKER] Datos recibidos: {req}")

        # Procesar operación de sumatoria de cuadrados (distribuida)
        if op == "sum_squares":
            a = int(req.get("a"))
            b = int(req.get("b"))
            print(f"[WORKER] Calculando sumatoria de cuadrados desde {a} hasta {b}")
            result = sum_squares(a, b)
            print(f"[WORKER] Resultado de sumatoria: {result}")
            
            response = {"ok": True, "result": result, "a": a, "b": b, "op": op}
            send_json(conn, response)
            print(f"[WORKER] Respuesta enviada: {response}")
            operation_count += 1
            print(f"[WORKER] ✅ Operación completada - Total procesadas: {operation_count}")

        # Procesar operaciones básicas (aritméticas)
        elif op in ("add", "sub", "mul", "div"):
            a = float(req.get("a"))
            b = float(req.get("b"))
            print(f"[WORKER] Operación {op}: {a} y {b}")

            if op == "add":
                result = a + b
                print(f"[WORKER] Suma: {a} + {b} = {result}")
            elif op == "sub":
                result = a - b
                print(f"[WORKER] Resta: {a} - {b} = {result}")
            elif op == "mul":
                result = a * b
                print(f"[WORKER] Multiplicación: {a} * {b} = {result}")
            elif op == "div":
                if b == 0:
                    print(f"[WORKER] ERROR: División por cero - operación no válida")
                    error_response = {"ok": False, "error": "División por cero - operación no válida", "a": a, "b": b, "op": op}
                    send_json(conn, error_response)
                    print(f"[WORKER] Respuesta de error enviada: {error_response}")
                    return operation_count  # Salir sin incrementar contador
                result = a / b
                print(f"[WORKER] División: {a} / {b} = {result}")

            response = {"ok": True, "result": result, "a": a, "b": b, "op": op}
            send_json(conn, response)
            print(f"[WORKER] Respuesta enviada: {response}")
            operation_count += 1
            print(f"[WORKER] ✅ Operación completada - Total procesadas: {operation_count}")

        else:
            error_msg = f"operación no soportada: {op}"
            print(f"[WORKER] ERROR: {error_msg}")
            send_json(conn, {"ok": False, "error": error_msg})

    except Exception as e:
        error_msg = str(e)
        print(f"[WORKER] ERROR durante procesamiento: {error_msg}")
        try:
            send_json(conn, {"ok": False, "error": error_msg})
        except Exception:
            print(f"[WORKER] ERROR: No se pudo enviar respuesta de error")
            pass
    finally:
        print(f"[WORKER] Cerrando conexión con {addr}")
        conn.close()
    
    return operation_count

def main():
    """
    Función principal del worker.
    Configura el servidor y espera conexiones del coordinador.
    """
    parser = argparse.ArgumentParser(description="Worker del sistema distribuido")
    parser.add_argument("--host", default="127.0.0.1", help="Dirección IP para escuchar")
    parser.add_argument("--port", type=int, default=6001, help="Puerto para escuchar")
    args = parser.parse_args()

    print(f"[WORKER] Iniciando worker en {args.host}:{args.port}")
    print(f"[WORKER] Esperando conexiones del coordinador...")
    
    # Configurar el socket del servidor
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(5)
    
    print(f"[WORKER] ✅ Worker listo y escuchando en {args.host}:{args.port}")
    print(f"[WORKER] Presiona Ctrl+C para detener el worker")
    
    # Contador de operaciones para estadísticas
    operation_count = 0
    
    try:
        while True:
            print(f"[WORKER] Esperando nueva conexión...")
            conn, addr = srv.accept()
            print(f"[WORKER] Conexión aceptada desde {addr}")
            operation_count = handle_connection(conn, addr, operation_count)
    except KeyboardInterrupt:
        print(f"\n[WORKER] Deteniendo worker...")
        print(f"[WORKER] 📊 RESUMEN: Procesé {operation_count} operaciones en total")
    finally:
        print(f"[WORKER] Cerrando servidor...")
        srv.close()
        print(f"[WORKER] Worker detenido")

if __name__ == "__main__":
    main()
