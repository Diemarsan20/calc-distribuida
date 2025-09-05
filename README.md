# 🖧 Sistema Distribuido Mínimo en Python

Este proyecto implementa un **sistema distribuido simple** usando únicamente **sockets TCP** y mensajes **JSONL** (JSON por línea).  

## ✨ Características
- **Operaciones básicas**: suma, resta, multiplicación y división.  
- **Operación distribuida**: cálculo de la sumatoria de cuadrados `1² + 2² + ... + n²`.  
- **Balanceo de carga**: round robin para operaciones simples.  
- **Soporte para N workers**: no se limita a 2.  
- **Tolerancia a fallos**: si un worker se cae, la tarea se reasigna a otro disponible.  

---

## 📂 Estructura del proyecto
```
common.py      # Funciones comunes de comunicación (send/recv JSON, sum_squares)
worker.py      # Worker que ejecuta operaciones
calc_server.py # Coordinador que reparte las tareas
client.py      # Cliente que envía solicitudes
README.md      # Documentación
```

---

## 🚀 Ejecución del sistema

### 1️⃣ Levantar los workers
En distintas terminales, inicia tantos workers como quieras (ejemplo con 3 workers):

```bash
python worker.py --host 127.0.0.1 --port 6001
python worker.py --host 127.0.0.1 --port 6002
python worker.py --host 127.0.0.1 --port 6003
```

### 2️⃣ Levantar el coordinador
En otra terminal, inicia el coordinador con la lista completa de workers:

```bash
python calc_server.py --host 127.0.0.1 --port 5000   --workers 127.0.0.1:6001 127.0.0.1:6002 127.0.0.1:6003
```

Salida esperada:
```
[calc-server] listening on 127.0.0.1:5000
Workers: ['127.0.0.1:6001', '127.0.0.1:6002', '127.0.0.1:6003']
```

### 3️⃣ Ejecutar el cliente
En otra terminal, puedes enviar operaciones al sistema.

---

## 🧮 Operaciones disponibles

### 🔹 Operaciones básicas
```bash
python client.py --op add --a 10 --b 5
# {"ok": true, "result": 15.0, "a": 10.0, "b": 5.0, "op": "add"}

python client.py --op sub --a 20 --b 7
# {"ok": true, "result": 13.0, "a": 20.0, "b": 7.0, "op": "sub"}

python client.py --op mul --a 6 --b 9
# {"ok": true, "result": 54.0, "a": 6.0, "b": 9.0, "op": "mul"}

python client.py --op div --a 10 --b 2
# {"ok": true, "result": 5.0, "a": 10.0, "b": 2.0, "op": "div"}

python client.py --op div --a 10 --b 0
# {"ok": false, "error": "División por cero"}
```

### 🔹 Operación distribuida: sumatoria de cuadrados
```bash
python client.py --op sum_squares --n 9
```

Si tienes 3 workers:
```json
{
  "ok": true,
  "result": 285,
  "parts": [
    {"a": 1, "b": 3, "result": 14},
    {"a": 4, "b": 6, "result": 77},
    {"a": 7, "b": 9, "result": 194}
  ]
}
```

---

## 🔄 Tolerancia a fallos

El sistema implementa **reintentos automáticos**:
- Si un worker **falla o está caído**, el coordinador prueba con otro.  
- Mientras quede al menos **un worker vivo**, las operaciones se completan.  
- Si **todos los workers caen**, el cliente recibe:
  ```json
  {"ok": false, "error": "ningún worker disponible"}
  ```

### Ejemplo:
- Workers: 6001, 6002, 6003.  
- Se apaga el worker `6002`.  
- Cliente ejecuta:
  ```bash
  python client.py --op sum_squares --n 9
  ```
- Coordinador detecta que `6002` no responde y reasigna su rango (`4..6`) a otro worker.  
- Resultado final:
  ```json
  {
    "ok": true,
    "result": 285,
    "parts": [
      {"a": 1, "b": 3, "result": 14},
      {"a": 4, "b": 6, "result": 77},
      {"a": 7, "b": 9, "result": 194}
    ]
  }
  ```

✔ La operación se completa correctamente a pesar de la falla.

---

## 📐 Diseño del sistema

- **Cliente** → envía la operación (ej. `add`, `sum_squares`).  
- **Coordinador (`calc_server.py`)** → recibe solicitudes, decide cómo repartirlas y agrega resultados.  
- **Workers (`worker.py`)** → ejecutan operaciones matemáticas.  
- **Comunicación** → TCP con mensajes JSONL.  

### Estrategia de distribución
- **Operaciones básicas (add, sub, mul, div)** → round robin entre workers.  
- **Sumatoria de cuadrados** → el rango `1..n` se divide equitativamente entre los workers configurados.  

---

## 📊 Ejemplo visual

```
Cliente
   |
   v
[ Coordinador ] -- round robin --> [ Worker 1 ]
       |                |--> [ Worker 2 ]
       |                |--> [ Worker 3 ]
       |
       +--> Combina resultados y responde al Cliente
```
---
