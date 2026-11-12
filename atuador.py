"""Atuador simulado. Recebe comandos das tres replicas e aplica o da maioria.

Uso: python atuador.py refrigeracao <cadeira>   (valvula: valor de 0 a 100 %)
     python atuador.py alarme                   (valor 0 ou 1)
     python atuador.py parada                   (valor 0 ou 1)

Comando recebido: {"valor": <numero>}
O comando leva sempre o valor final, nunca um incremento.
Assim, receber o mesmo comando duas vezes nao muda nada (idempotencia).
"""

import json
import sys

import comum

tipo = sys.argv[1]

if tipo == "refrigeracao":
    cadeira = int(sys.argv[2])
    nome = f"atuador-refrigeracao-c{cadeira}"
    atuador = comum.atuador_refrigeracao(cadeira)
elif tipo == "alarme":
    nome = "atuador-alarme"
    atuador = comum.ATUADOR_ALARME
elif tipo == "parada":
    nome = "atuador-parada"
    atuador = comum.ATUADOR_PARADA
else:
    sys.exit(f"tipo de atuador desconhecido: {tipo}")

log = comum.criar_log(nome)
valor_atual = 0  # o que o atuador esta aplicando agora
votos = {}       # replica -> ultimo valor que ela comandou


def publicar_aplicado(conexao_mqtt):
    """Informa o que o atuador esta de fato aplicando (retido: quem assinar depois recebe)."""
    conexao_mqtt.publish(comum.topico_aplicado(atuador), json.dumps({"valor": valor_atual}),
                         qos=comum.QOS, retain=True)


def ao_conectar(conexao_mqtt, dados, flags, codigo, propriedades):
    filtro = comum.filtro_comandos(atuador)
    conexao_mqtt.subscribe(filtro, qos=comum.QOS)
    publicar_aplicado(conexao_mqtt)
    log.info("conectado ao broker; assinando %s", filtro)


def ao_receber(conexao_mqtt, dados, mensagem):
    global valor_atual
    # O ultimo nivel do topico diz qual replica mandou o comando.
    replica = mensagem.topic.split("/")[-1]
    votos[replica] = json.loads(mensagem.payload)["valor"]

    vencedor = comum.votar(list(votos.values()))
    if vencedor is None:
        log.info("comando da replica %s; votos %s; sem maioria, mantido o valor %s",
                 replica, votos, valor_atual)
    elif vencedor == valor_atual:
        log.info("comando da replica %s; votos %s; maioria confirma o valor %s",
                 replica, votos, valor_atual)
    else:
        log.info("comando da replica %s; votos %s; maioria muda o valor %s -> %s",
                 replica, votos, valor_atual, vencedor)
        valor_atual = vencedor
        publicar_aplicado(conexao_mqtt)


conexao_mqtt = comum.conectar(nome, ao_conectar, ao_receber)

try:
    conexao_mqtt.loop_forever()  # so espera comandos
except KeyboardInterrupt:
    pass
finally:
    conexao_mqtt.disconnect()
    log.info("encerrado")
