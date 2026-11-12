"""Controlador de processo: recebe, filtra, grava, decide e comanda.
Atende tambem o cliente, por um objeto remoto (Pyro5).

Uso: python controlador.py <numero da replica: 1, 2 ou 3>
     python controlador.py <numero> mentir         (teste: replica que mente sempre)
     python controlador.py <numero> intermitente   (teste: mente 5 s, acerta 5 s)
"""

import json
import sys
import threading
import time
from collections import deque
from datetime import datetime

import Pyro5
from Pyro5.api import Daemon, Proxy, expose
from Pyro5.errors import CommunicationError

import comum
from armazenamento import Armazenamento

# Parametros da regra de decisao (parametros de simulacao).
LIMITE_ALERTA = 80.0    # graus C
LIMITE_CRITICO = 100.0  # graus C
TAXA_ALERTA = 2.0       # graus C por segundo: entra em alerta
TAXA_RETORNO = 0.5      # graus C por segundo: so sai do alerta abaixo disto
TAXA_VALE_ACIMA = 55.0  # graus C: abaixo disto a subida e reaquecimento normal
JANELA = 5              # leituras usadas para calcular a taxa de subida

# Estados em numeros para que "o pior caso" seja simplesmente o maior.
NORMAL, ALERTA, CRITICO = 0, 1, 2
NOME_ESTADO = {NORMAL: "normal", ALERTA: "alerta", CRITICO: "critico"}

VALVULA_NORMAL = 50
VALVULA_MAXIMA = 100

# Cada replica tem o seu nome, o seu arquivo de banco e a sua porta.
numero = int(sys.argv[1])
nome = comum.nome_controlador(numero)
log = comum.criar_log(nome)
armazenamento = Armazenamento(f"dados/{nome}.db")

# Modos de teste: a replica decide certo por dentro, mas MENTE no que sai dela.
# Quando mente, diz que esta tudo normal e que a linha esta liberada.
#   "mentir":       mente sempre (como uma replica invadida)
#   "intermitente": mente 5 segundos, acerta 5 segundos (erro intermitente)
MODO = sys.argv[2] if len(sys.argv) > 2 else "correto"
if MODO != "correto":
    log.info("MODO DE TESTE: replica defeituosa (%s)", MODO)


def mentir_agora():
    """Diz se a saida deste instante sera falsa."""
    if MODO == "mentir":
        return True
    if MODO == "intermitente":
        return int(time.time()) % 10 < 5
    return False

# Duas threads mexem nas variaveis abaixo: a que trata as leituras (MQTT) e a
# que atende o cliente (Pyro5). Quem vai mexer segura o mutex (exclusao mutua); a outra espera.
# Nao confundir com "parada_ativa", que e regra do processo.
mutex = threading.Lock()

# Memoria curta: perde-se se o controlador cair.
ultimo_seq = {}          # (cadeira, cilindro) -> ultimo seq aceito
janelas = {}             # (cadeira, cilindro) -> ultimas leituras (instante, temperatura)
estado_cilindro = {}     # (cadeira, cilindro) -> NORMAL, ALERTA ou CRITICO
ultima_temperatura = {}  # (cadeira, cilindro) -> ultima temperatura aceita
comandos_enviados = {}   # atuador -> ultimo valor comandado

# A parada ativa fica no disco: depois de ligada, so o operador desliga (rearme).
# Um controlador que cai e volta nao pode religar a linha sozinho.
parada_ativa = armazenamento.ler_persistente("parada_ativa", "0") == "1"
if parada_ativa:
    log.info("iniciando com a parada ativa (lida do armazenamento)")


def registrar(tipo, descricao):
    log.info("%s: %s", tipo, descricao)
    armazenamento.gravar_evento(tipo, descricao)


def taxa_de_subida(janela):
    """Graus C por segundo entre a leitura mais antiga e a mais nova da janela."""
    if len(janela) < 2:
        return 0.0
    instante_antigo, temperatura_antiga = janela[0]
    instante_novo, temperatura_nova = janela[-1]
    segundos = (instante_novo - instante_antigo).total_seconds()
    if segundos <= 0:
        return 0.0
    return (temperatura_nova - temperatura_antiga) / segundos


def classificar(temperatura, taxa, estado_anterior):
    if temperatura >= LIMITE_CRITICO:
        return CRITICO
    if temperatura >= LIMITE_ALERTA:
        return ALERTA
    # A taxa so conta perto da temperatura de trabalho: uma linha que retoma
    # depois de parada aquece rapido de 40 para 60 graus sem haver falha.
    if taxa >= TAXA_ALERTA and temperatura >= TAXA_VALE_ACIMA:
        return ALERTA
    # Histerese: quem ja estava em alerta so volta ao normal
    # quando a temperatura praticamente parou de subir.
    if estado_anterior != NORMAL and taxa >= TAXA_RETORNO:
        return ALERTA
    return NORMAL


def comandar(atuador, valor):
    """Publica o comando, no topico desta replica, somente se o valor mudou."""
    if mentir_agora():
        valor = VALVULA_NORMAL if "refrigeracao" in atuador else 0
    if comandos_enviados.get(atuador) == valor:
        return
    comandos_enviados[atuador] = valor
    topico = comum.topico_comando(atuador, numero)
    # retain=True: o broker guarda o ultimo comando de cada topico e o entrega
    # a quem assinar depois. Um atuador que liga atrasado recebe o valor vigente.
    conexao_mqtt.publish(topico, json.dumps({"valor": valor}), qos=comum.QOS, retain=True)
    registrar("comando", f"{topico} valor={valor}")


def atualizar_atuadores():
    """Do cilindro para o conjunto vale sempre o pior caso (o maior).
    Chamada depois de cada leitura e depois de cada acao do operador."""
    global parada_ativa

    estado_linha = NORMAL
    for cadeira in comum.CADEIRAS:
        estado_cadeira = max(estado_cilindro.get((cadeira, c), NORMAL) for c in comum.CILINDROS)
        valvula = VALVULA_MAXIMA if estado_cadeira != NORMAL else VALVULA_NORMAL
        comandar(comum.atuador_refrigeracao(cadeira), valvula)
        estado_linha = max(estado_linha, estado_cadeira)

    if estado_linha == CRITICO and not parada_ativa:
        parada_ativa = True
        armazenamento.gravar_persistente("parada_ativa", "1")
    comandar(comum.ATUADOR_PARADA, 1 if parada_ativa else 0)

    # O alarme fica ligado enquanto a linha estiver parada aguardando o operador.
    comandar(comum.ATUADOR_ALARME, 1 if estado_linha != NORMAL or parada_ativa else 0)


# ---------- Entrada 1: leituras dos sensores (MQTT) ----------

def ao_conectar(conexao_mqtt, dados, flags, codigo, propriedades):
    conexao_mqtt.subscribe(comum.FILTRO_TEMPERATURAS, qos=comum.QOS)
    log.info("conectado ao broker; assinando %s", comum.FILTRO_TEMPERATURAS)


def ao_receber(conexao_mqtt, dados, mensagem):
    with mutex:
        # 1. Receber: o texto JSON volta a ser um dicionario.
        leitura = json.loads(mensagem.payload)
        chave = (leitura["cadeira"], leitura["cilindro"])
        seq = leitura["seq"]

        # 2. Filtrar pelo seq.
        ultimo = ultimo_seq.get(chave)
        if ultimo is not None:
            if seq == ultimo:
                registrar("duplicata", f"{chave} seq={seq} descartada")
                return
            if seq > ultimo + 1:
                registrar("perda", f"{chave} faltam seq {ultimo + 1} a {seq - 1}")
            if seq < ultimo:
                registrar("reinicio", f"{chave} sensor reiniciou (seq {ultimo} -> {seq})")
                janelas[chave].clear()
        ultimo_seq[chave] = seq

        # 3. Gravar.
        armazenamento.gravar_leitura(leitura)

        # 4. Decidir o estado do cilindro.
        janela = janelas.setdefault(chave, deque(maxlen=JANELA))
        janela.append((datetime.fromisoformat(leitura["instante"]), leitura["temperatura"]))
        taxa = taxa_de_subida(janela)
        anterior = estado_cilindro.get(chave, NORMAL)
        novo = classificar(leitura["temperatura"], taxa, anterior)
        if novo != anterior:
            registrar("estado", f"{chave} {NOME_ESTADO[anterior]} -> {NOME_ESTADO[novo]} "
                                f"(temperatura={leitura['temperatura']}, taxa={taxa:.1f})")
        estado_cilindro[chave] = novo
        ultima_temperatura[chave] = leitura["temperatura"]

        # 5. Comandar.
        atualizar_atuadores()


# ---------- Acoes do operador ----------

def executar_parada():
    global parada_ativa
    if parada_ativa:
        return {"aceito": True, "mensagem": "a linha ja estava parada"}
    parada_ativa = True
    armazenamento.gravar_persistente("parada_ativa", "1")
    registrar("operador", "parada manual")
    atualizar_atuadores()
    return {"aceito": True, "mensagem": "linha parada"}


def executar_rearme():
    global parada_ativa
    if not parada_ativa:
        return {"aceito": True, "mensagem": "a linha ja estava liberada"}
    # So rearma conhecendo os 6 cilindros e com todos normais.
    for cadeira in comum.CADEIRAS:
        for cilindro in comum.CILINDROS:
            chave = (cadeira, cilindro)
            if chave not in ultima_temperatura:
                motivo = f"sem leitura do cilindro {cilindro} da cadeira {cadeira}"
            elif estado_cilindro[chave] != NORMAL:
                motivo = (f"cilindro {cilindro} da cadeira {cadeira} em "
                          f"{NOME_ESTADO[estado_cilindro[chave]]}")
            else:
                continue
            registrar("operador", f"rearme recusado: {motivo}")
            return {"aceito": False, "mensagem": f"recusado: {motivo}"}
    parada_ativa = False
    armazenamento.gravar_persistente("parada_ativa", "0")
    registrar("operador", "rearme aceito")
    atualizar_atuadores()
    return {"aceito": True, "mensagem": "linha liberada"}


def executar_uma_vez(pedido, acao):
    """No maximo uma vez: um pedido cujo identificador ja foi executado
    nao e executado de novo; devolve-se a resposta guardada."""
    resposta = armazenamento.ler_pedido(pedido)
    if resposta is not None:
        registrar("pedido", f"{pedido} repetido; devolvida a resposta guardada")
        return resposta
    resposta = acao()
    armazenamento.gravar_pedido(pedido, resposta)
    return resposta


# ---------- Entrada 2: chamadas do cliente (Pyro5) ----------

@expose
class ControladorRemoto:
    """Os metodos desta classe sao os unicos que o cliente consegue chamar."""

    def obter_painel(self):
        with mutex:
            cilindros = []
            for cadeira in comum.CADEIRAS:
                for cilindro in comum.CILINDROS:
                    chave = (cadeira, cilindro)
                    cilindros.append({
                        "cadeira": cadeira,
                        "cilindro": cilindro,
                        "temperatura": ultima_temperatura.get(chave),  # None = sem leitura
                        "estado": NOME_ESTADO[estado_cilindro.get(chave, NORMAL)],
                    })
            painel = {
                "cilindros": cilindros,
                "valvulas": [comandos_enviados.get(comum.atuador_refrigeracao(c)) for c in comum.CADEIRAS],
                "alarme": comandos_enviados.get(comum.ATUADOR_ALARME),
                "parada": parada_ativa,
            }
            if mentir_agora():
                for cilindro in painel["cilindros"]:
                    cilindro["temperatura"] = 60.0
                    cilindro["estado"] = NOME_ESTADO[NORMAL]
                painel["parada"] = False
            return painel

    def obter_eventos(self, quantidade):
        with mutex:
            return armazenamento.ler_eventos(quantidade)

    def obter_resumo(self):
        """Retrato curto do armazenamento, para comparar as replicas."""
        with mutex:
            return {"leituras": armazenamento.ler_resumo(),
                    "parada": False if mentir_agora() else parada_ativa}

    def obter_copia(self, desde):
        """Chamado por uma colega que reiniciou: o que ela perdeu enquanto esteve fora."""
        with mutex:
            return {"leituras": armazenamento.ler_leituras_desde(desde),
                    "pedidos": armazenamento.ler_pedidos(),
                    "parada": False if mentir_agora() else parada_ativa}

    def parar_linha(self, pedido):
        with mutex:
            return executar_uma_vez(pedido, executar_parada)

    def rearmar(self, pedido):
        with mutex:
            return executar_uma_vez(pedido, executar_rearme)


# ---------- Inicio ----------

def recuperar_estado(desde):
    """Transferencia de estado: pede as colegas o que se perdeu enquanto esteve fora."""
    global parada_ativa
    paradas = []    # o que cada colega respondeu sobre a parada
    copiou = False  # leituras e pedidos vem da primeira colega que responder
    for colega in comum.REPLICAS:
        if colega == numero:
            continue
        try:
            with Proxy(comum.uri_controlador(colega)) as proxy:
                proxy._pyroTimeout = 3.0  # segundos de espera pela resposta
                copia = proxy.obter_copia(desde)
        except CommunicationError:
            log.info("recuperacao: %s sem resposta", comum.nome_controlador(colega))
            continue
        paradas.append(copia["parada"])
        if not copiou:
            for leitura in copia["leituras"]:
                armazenamento.gravar_leitura(leitura)
            for pedido, resposta in copia["pedidos"]:
                armazenamento.gravar_pedido(pedido, resposta)
            copiou = True
            registrar("recuperacao", f"{len(copia['leituras'])} leituras recebidas de "
                                     f"{comum.nome_controlador(colega)}")

    if not paradas:
        log.info("recuperacao: nenhuma colega respondeu; seguindo com o proprio armazenamento")
        return
    # Duas respostas iguais: adota. Uma resposta so: vale se for igual ao proprio
    # disco (dois de acordo). Em qualquer desacordo, o lado seguro: linha parada.
    if len(paradas) == 2 and paradas[0] == paradas[1]:
        nova, motivo = paradas[0], "as duas colegas concordam"
    elif len(paradas) == 1 and paradas[0] == parada_ativa:
        nova, motivo = parada_ativa, "a unica colega que respondeu concorda com o proprio disco"
    else:
        nova, motivo = True, f"desacordo (colegas {paradas}, disco {parada_ativa}); adotado o lado seguro"
    if nova != parada_ativa:
        parada_ativa = nova
        armazenamento.gravar_persistente("parada_ativa", "1" if parada_ativa else "0")
    registrar("recuperacao", f"parada_ativa={parada_ativa} ({motivo})")


# O mutex fica preso durante todo o inicio. As leituras que chegarem do broker
# nesse intervalo esperam em "ao_receber" e so sao tratadas depois da
# recuperacao, ja com a parada ativa correta.
with mutex:
    desde = armazenamento.ultimo_instante()
    # As leituras passam a ser tratadas numa thread criada pela biblioteca MQTT.
    conexao_mqtt = comum.conectar(nome, ao_conectar, ao_receber)
    conexao_mqtt.loop_start()
    recuperar_estado(desde)

# As chamadas do cliente sao atendidas aqui, na thread principal, uma por vez.
Pyro5.config.SERVERTYPE = "multiplex"
daemon = Daemon(host=comum.CONTROLADOR_HOST, port=comum.porta_controlador(numero))
daemon.register(ControladorRemoto(), objectId=comum.CONTROLADOR_OBJETO)
log.info("objeto remoto disponivel em %s", comum.uri_controlador(numero))

try:
    daemon.requestLoop()
except KeyboardInterrupt:
    pass
finally:
    daemon.close()
    conexao_mqtt.loop_stop()
    conexao_mqtt.disconnect()
    log.info("encerrado")
