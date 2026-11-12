"""Experimento: onde colocar o subscribe.

Dois assinantes do mesmo topico:
  ERRADO: assina uma vez, logo depois do connect.
  CERTO:  assina dentro de ao_conectar (roda a cada conexao).

No meio do experimento o broker e reiniciado.
Uso: python experimentos/reconexao.py   (o broker precisa estar no ar)
"""

import subprocess
import time

import paho.mqtt.client as mqtt

TOPICO = "experimento/reconexao"
recebidas = {"ERRADO": [], "CERTO": []}


def novo_cliente(nome):
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"exp-{nome}")


def guardar(nome):
    def ao_receber(cliente, dados, mensagem):
        recebidas[nome].append(int(mensagem.payload))
    return ao_receber


# ----- ERRADO: subscribe logo depois do connect -----
errado = novo_cliente("errado")
errado.on_message = guardar("ERRADO")
errado.on_connect = lambda c, d, f, codigo, p: print("  ERRADO conectou (nao assina aqui)")
errado.connect("localhost", 1883)
errado.subscribe(TOPICO, qos=1)        # executa UMA vez na vida do programa
errado.loop_start()

# ----- CERTO: subscribe dentro de ao_conectar -----
def ao_conectar(cliente, dados, flags, codigo, propriedades):
    cliente.subscribe(TOPICO, qos=1)   # executa a CADA conexao
    print("  CERTO conectou e assinou")

certo = novo_cliente("certo")
certo.on_message = guardar("CERTO")
certo.on_connect = ao_conectar
certo.connect("localhost", 1883)
certo.loop_start()

# ----- Quem publica: uma mensagem numerada por segundo -----
publicador = novo_cliente("publicador")
publicador.connect("localhost", 1883)
publicador.loop_start()

time.sleep(1)
for numero in range(1, 21):
    if numero == 6:
        print(">>> reiniciando o broker")
        subprocess.run(["docker", "restart", "laminacao-broker"], capture_output=True)
        time.sleep(3)  # tempo para os tres clientes reconectarem
    publicador.publish(TOPICO, str(numero), qos=1)
    time.sleep(1)

print()
print("Publicadas: 1 a 20 (broker reiniciado antes da 6)")
for nome, numeros in recebidas.items():
    print(f"{nome:6} recebeu {len(numeros):2}: {numeros}")
