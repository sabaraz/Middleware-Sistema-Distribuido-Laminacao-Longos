"""Sensor simulado de temperatura de um cilindro.

Uso: python sensor.py <cadeira> <cilindro>
Ex.: python sensor.py 2 superior
"""

import json
import random
import sys
import time
from datetime import datetime, timezone

import comum

TEMPERATURA_NORMAL = 60.0   # graus C, parametro de simulacao
TEMPERATURA_PARADA = 40.0   # graus C, linha parada: sem aco quente
SUBIDA_EM_FALHA = 3.0       # graus C por segundo, falha com valvula abaixo de 100
SUBIDA_COM_REFORCO = 1.0    # graus C por segundo, falha com valvula em 100
TEMPERATURA_MAXIMA = 150.0  # teto da simulacao
INTERVALO = 1.0             # segundos entre leituras

cadeira = int(sys.argv[1])
cilindro = sys.argv[2]
nome = f"sensor-c{cadeira}-{cilindro}"
log = comum.criar_log(nome)

# O "mundo fisico" visto por este cilindro. Alterado pela thread de rede.
em_falha = False  # falha de refrigeracao provocada pelo topico de simulacao
valvula = 0       # abertura da valvula da cadeira (0 a 100)
parada = False    # linha parada

TOPICO_FALHA = comum.topico_falha(cadeira, cilindro)
# A simulacao reage ao que os atuadores de fato aplicaram, nao aos comandos.
TOPICO_VALVULA = comum.topico_aplicado(comum.atuador_refrigeracao(cadeira))
TOPICO_PARADA = comum.topico_aplicado(comum.ATUADOR_PARADA)


def ao_conectar(conexao_mqtt, dados, flags, codigo, propriedades):
    conexao_mqtt.subscribe(TOPICO_FALHA, qos=comum.QOS)
    # Simulacao da fisica: numa usina o sensor nao ouve a valvula nem a parada;
    # e a agua e a ausencia de aco quente que mudam a temperatura.
    conexao_mqtt.subscribe(TOPICO_VALVULA, qos=comum.QOS)
    conexao_mqtt.subscribe(TOPICO_PARADA, qos=comum.QOS)
    log.info("conectado ao broker")


def ao_receber(conexao_mqtt, dados, mensagem):
    global em_falha, valvula, parada
    if mensagem.topic == TOPICO_FALHA:
        em_falha = mensagem.payload.decode() == "1"
        log.info("simulacao: falha de refrigeracao = %s", em_falha)
    elif mensagem.topic == TOPICO_VALVULA:
        valvula = json.loads(mensagem.payload)["valor"]
        log.info("simulacao: valvula = %s", valvula)
    elif mensagem.topic == TOPICO_PARADA:
        parada = json.loads(mensagem.payload)["valor"] == 1
        log.info("simulacao: parada = %s", parada)


conexao_mqtt = comum.conectar(nome, ao_conectar, ao_receber)
conexao_mqtt.loop_start()  # a rede roda em segundo plano; o laco abaixo so mede e publica

temperatura = TEMPERATURA_NORMAL
seq = 0

try:
    while True:
        # Modelo fisico minimo, em ordem de prioridade:
        # linha parada -> esfria; falha -> sobe (menos com a valvula em 100);
        # sem falha -> volta aos poucos para a temperatura normal.
        if parada:
            temperatura += (TEMPERATURA_PARADA - temperatura) * 0.2
        elif em_falha:
            temperatura += SUBIDA_COM_REFORCO if valvula >= 100 else SUBIDA_EM_FALHA
        else:
            temperatura += (TEMPERATURA_NORMAL - temperatura) * 0.2
        temperatura += random.uniform(-0.3, 0.3)  # ruido de medicao
        temperatura = min(temperatura, TEMPERATURA_MAXIMA)

        seq += 1
        leitura = {
            "cadeira": cadeira,
            "cilindro": cilindro,
            "temperatura": round(temperatura, 1),
            "seq": seq,
            "instante": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }
        # Serializacao: o dicionario vira texto JSON para ser transportado.
        conexao_mqtt.publish(comum.topico_temperatura(cadeira, cilindro), json.dumps(leitura), qos=comum.QOS)
        log.info("publicou seq=%d temperatura=%.1f", seq, leitura["temperatura"])

        time.sleep(INTERVALO)
except KeyboardInterrupt:
    pass
finally:
    conexao_mqtt.loop_stop()
    conexao_mqtt.disconnect()
    log.info("encerrado")
