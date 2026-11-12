"""O que todos os programas do projeto compartilham:
endereco do broker, nomes dos topicos, log e conexao MQTT."""

import logging
import os
import time

import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORTA = 1883

# QoS 1 em todos os topicos: nao perde, pode duplicar.
# Duplicata de leitura e descartada pelo "seq"; de comando, pela idempotencia.
QOS = 1

CADEIRAS = [1, 2, 3]
CILINDROS = ["superior", "inferior"]

# As tres replicas do controlador. Sao iguais; so mudam nome, banco e porta.
REPLICAS = [1, 2, 3]
CONTROLADOR_HOST = "localhost"
CONTROLADOR_OBJETO = "controlador"


def nome_controlador(numero):
    return f"controlador-{numero}"


def porta_controlador(numero):
    return 9090 + numero  # 9091, 9092, 9093


def uri_controlador(numero):
    """Endereco do objeto remoto (Pyro5): nome do objeto, maquina e porta."""
    return f"PYRO:{CONTROLADOR_OBJETO}@{CONTROLADOR_HOST}:{porta_controlador(numero)}"


# ---------- Topicos do processo ----------

def topico_temperatura(cadeira, cilindro):
    return f"laminacao/cadeira/{cadeira}/cilindro/{cilindro}/temperatura"


# Um unico filtro recebe os 6 sensores ("+" vale por um nivel).
FILTRO_TEMPERATURAS = "laminacao/cadeira/+/cilindro/+/temperatura"


# Cada atuador tem um endereco. Abaixo dele ficam os topicos de comando e o do valor aplicado.
def atuador_refrigeracao(cadeira):
    return f"laminacao/cadeira/{cadeira}/refrigeracao"


# Acoes do conjunto ficam em "linha": nao existe alarme ou parada de uma cadeira so.
ATUADOR_ALARME = "laminacao/linha/alarme"
ATUADOR_PARADA = "laminacao/linha/parada"


def topico_comando(atuador, replica):
    """Cada replica comanda num topico proprio, para o atuador saber quem mandou."""
    return f"{atuador}/comando/{replica}"


def filtro_comandos(atuador):
    """Os comandos das tres replicas para um atuador."""
    return f"{atuador}/comando/+"


def topico_aplicado(atuador):
    """O valor que o atuador de fato aplicou, depois do voto."""
    return f"{atuador}/aplicado"


# ---------- Voto ----------

MAIORIA = 2  # de 3 replicas


def votar(valores):
    """Devolve o valor que aparece em pelo menos MAIORIA dos valores recebidos.
    Sem maioria, devolve None."""
    for candidato in valores:
        iguais = sum(1 for valor in valores if valor == candidato)
        if iguais >= MAIORIA:
            return candidato
    return None


# ---------- Topico da simulacao ----------

def topico_falha(cadeira, cilindro):
    """Nao faz parte do processo. Faz o papel do mundo fisico:
    permite provocar uma falha de refrigeracao em um cilindro simulado."""
    return f"simulacao/cadeira/{cadeira}/cilindro/{cilindro}/falha"


# ---------- Log ----------

def criar_log(nome):
    """Log com data e hora, na tela e no arquivo logs/<nome>.log."""
    os.makedirs("logs", exist_ok=True)
    log = logging.getLogger(nome)
    log.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s UTC [%(name)s] %(message)s")
    formato.converter = time.gmtime  # mesma referencia de tempo do campo "instante"
    for destino in (logging.StreamHandler(), logging.FileHandler(f"logs/{nome}.log", encoding="utf-8")):
        destino.setFormatter(formato)
        log.addHandler(destino)
    return log


# ---------- Conexao ----------

def conectar(nome, ao_conectar=None, ao_receber=None):
    """Conecta ao broker e devolve a conexao MQTT.

    ao_conectar: funcao chamada a cada conexao (inclusive reconexao);
                 e nela que as assinaturas sao feitas.
    ao_receber:  funcao chamada a cada mensagem recebida.
    """
    conexao_mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=nome)
    if ao_conectar:
        conexao_mqtt.on_connect = ao_conectar
    if ao_receber:
        conexao_mqtt.on_message = ao_receber
    conexao_mqtt.connect(BROKER_HOST, BROKER_PORTA)
    return conexao_mqtt
