"""
client.py - Cliente de usuario final.
Se conecta al coordinador y solicita una operación.
Ejemplos:
  python client.py --op add --a 10 --b 5
  python client.py --op div --a 8 --b 2
  python client.py --op sum_squares --n 1000000
"""
import argparse
import socket
from common import send_json, recv_json

def main():
    """
    Función principal del cliente.
    Se conecta al coordinador, envía una solicitud y muestra el resultado.
    """
    parser = argparse.ArgumentParser(description="Cliente del sistema distribuido")
    parser.add_argument("--host", default="127.0.0.1", help="Dirección IP del coordinador")
    parser.add_argument("--port", type=int, default=5000, help="Puerto del coordinador")
    parser.add_argument("--op", required=True, help="Operación: add, sub, mul, div, sum_squares")
    parser.add_argument("--a", type=float, help="Operando A (para add/sub/mul/div)")
    parser.add_argument("--b", type=float, help="Operando B (para add/sub/mul/div)")
    parser.add_argument("--n", type=int, help="Valor n (para sum_squares)")
    args = parser.parse_args()

    print(f"[CLIENT] Conectando al coordinador en {args.host}:{args.port}")
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((args.host, args.port))
        print(f"[CLIENT] ✅ Conectado al coordinador")
        
        # Preparar mensaje según la operación
        if args.op == "sum_squares":
            msg = {"op": args.op, "n": args.n}
            print(f"[CLIENT] Solicitando sumatoria de cuadrados para n={args.n}")
        else:
            msg = {"op": args.op, "a": args.a, "b": args.b}
            print(f"[CLIENT] Solicitando operación {args.op}: {args.a} y {args.b}")

        # Enviar solicitud
        print(f"[CLIENT] Enviando solicitud...")
        send_json(s, msg)
        
        # Recibir respuesta
        print(f"[CLIENT] Esperando respuesta...")
        resp = recv_json(s)
        
        # Mostrar resultado de forma amigable
        if resp.get("ok"):
            if args.op == "sum_squares":
                result = resp.get("result")
                print(f"\n🎯 RESULTADO: {result}")
            else:
                result = resp.get("result")
                op_symbol = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[args.op]
                print(f"\n🎯 RESULTADO: {args.a} {op_symbol} {args.b} = {result}")
        else:
            error = resp.get("error", "Error desconocido")
            if "División por cero" in error:
                print(f"\n❌ ERROR: La operación no se puede realizar - División por cero")
                print(f"   No es posible dividir {args.a} entre {args.b}")
            elif "sistema_temporalmente_ocupado" in error:
                print(f"\n⚠️ El sistema está temporalmente ocupado")
                print(f"   Por favor, intente nuevamente en unos momentos")
            else:
                # Ocultar errores técnicos del sistema al usuario
                print(f"\n⚠️ El sistema está temporalmente ocupado")
                print(f"   Por favor, intente nuevamente en unos momentos")
            
    except ConnectionRefusedError:
        print(f"\n⚠️ El sistema no está disponible en este momento")
        print(f"   Por favor, intente nuevamente más tarde")
    except Exception as e:
        print(f"\n⚠️ El sistema está temporalmente ocupado")
        print(f"   Por favor, intente nuevamente en unos momentos")
    finally:
        s.close()
        print(f"[CLIENT] Conexión cerrada")

if __name__ == "__main__":
    main()
