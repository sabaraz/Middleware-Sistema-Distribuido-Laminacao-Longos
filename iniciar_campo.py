"""Inicia o "campo" da simulacao: 6 sensores e 5 atuadores, cada um em seu processo.

Uso: python iniciar_campo.py      (Ctrl+C encerra todos)
"""

import subprocess
import sys

import comum

comandos = []
for cadeira in comum.CADEIRAS:
    for cilindro in comum.CILINDROS:
        comandos.append(["sensor.py", str(cadeira), cilindro])
    comandos.append(["atuador.py", "refrigeracao", str(cadeira)])
comandos.append(["atuador.py", "alarme"])
comandos.append(["atuador.py", "parada"])

processos = [subprocess.Popen([sys.executable] + comando) for comando in comandos]
print(f"{len(processos)} processos iniciados. Ctrl+C para encerrar.")

try:
    for processo in processos:
        processo.wait()
except KeyboardInterrupt:
    for processo in processos:
        processo.terminate()
