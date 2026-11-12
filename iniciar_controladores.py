"""Inicia as 3 replicas do controlador, cada uma em seu processo.

Uso: python iniciar_controladores.py      (Ctrl+C encerra todas)
"""

import subprocess
import sys

import comum

processos = [subprocess.Popen([sys.executable, "controlador.py", str(numero)]) for numero in comum.REPLICAS]
print(f"{len(processos)} replicas iniciadas. Ctrl+C para encerrar.")

try:
    for processo in processos:
        processo.wait()
except KeyboardInterrupt:
    for processo in processos:
        processo.terminate()
