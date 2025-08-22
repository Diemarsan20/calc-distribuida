# client.py
import argparse, socket, json
from netutils import send_json, recv_lines

def main():
    ap = argparse.ArgumentParser(description="Cliente para sistema de cálculo distribuido")
    ap.add_argument("--coord-host", required=True, help="IP del coordinador")
    ap.add_argument("--client-port", type=int, default=5002, help="Puerto del coordinador para clientes")
    sub = ap.add_subparsers(dest="cmd", required=True, help="Operación a realizar")

    # Comando sum_range (suma de rango)
    ssum = sub.add_parser("sum_range", help="Suma [start..end] en paralelo")
    ssum.add_argument("--start", type=int, required=True)
    ssum.add_argument("--end", type=int, required=True)
    ssum.add_argument("--chunks", type=int, default=2)

    # Comando sum (suma de números)
    sum_cmd = sub.add_parser("sum", help="Suma una lista de números")
    sum_cmd.add_argument("numbers", nargs="+", type=float, help="Números a sumar")
    sum_cmd.add_argument("--chunks", type=int, default=2)

    # Comando multiply (multiplicación de números)
    mult_cmd = sub.add_parser("multiply", help="Multiplica una lista de números")
    mult_cmd.add_argument("numbers", nargs="+", type=float, help="Números a multiplicar")
    mult_cmd.add_argument("--chunks", type=int, default=2)

    # Comando subtract (resta de números)
    sub_cmd = sub.add_parser("subtract", help="Resta números (primero - resto)")
    sub_cmd.add_argument("numbers", nargs="+", type=float, help="Números a restar")
    sub_cmd.add_argument("--chunks", type=int, default=2)

    # Comando divide (división de números)
    div_cmd = sub.add_parser("divide", help="Divide números (primero / resto)")
    div_cmd.add_argument("numbers", nargs="+", type=float, help="Números a dividir")
    div_cmd.add_argument("--chunks", type=int, default=2)

    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((args.coord_host, args.client_port))

    if args.cmd == "sum_range":
        payload = {"start": args.start, "end": args.end}
        send_json(sock, {"type":"job","op":"sum_range","payload":payload,"chunks":args.chunks})
    elif args.cmd in ["sum", "multiply", "subtract", "divide"]:
        payload = {"numbers": args.numbers}
        send_json(sock, {"type":"job","op":args.cmd,"payload":payload,"chunks":args.chunks})

    buf = bytearray()
    # Esperar respuesta final del coordinador
    while True:
        msgs = recv_lines(sock, buf)
        if not msgs:
            break
        for m in msgs:
            t = m.get("type")
            if t == "job_done":
                print(f"RESULTADO: {m['result']} (task_id={m.get('task_id')})")
                sock.close()
                return
            elif t == "job_error":
                print("ERROR:", m.get("error"))
                sock.close()
                return

if __name__ == "__main__":
    main()
