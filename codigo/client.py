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
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--op", required=True, help="Operación: add, sub, mul, div, sum_squares")
    parser.add_argument("--a", type=float, help="Operando A (para add/sub/mul/div)")
    parser.add_argument("--b", type=float, help="Operando B (para add/sub/mul/div)")
    parser.add_argument("--n", type=int, help="Valor n (para sum_squares)")
    args = parser.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((args.host, args.port))
    try:
        if args.op == "sum_squares":
            msg = {"op": args.op, "n": args.n}
        else:
            msg = {"op": args.op, "a": args.a, "b": args.b}

        send_json(s, msg)
        resp = recv_json(s)
        print(resp)
    finally:
        s.close()

if __name__ == "__main__":
    main()
