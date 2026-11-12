"""Cliente do operador, no terminal. Fala somente com os controladores,
por chamadas de metodo (Pyro5). Nunca fala com o broker MQTT.
So aceita o que pelo menos duas das tres replicas disserem igual.

Uso: python cliente.py
"""

import time
import uuid

import Pyro5
from Pyro5.api import Proxy
from Pyro5.errors import CommunicationError

import comum

# Sem isto, uma chamada a um controlador que nao responde esperaria para sempre.
Pyro5.config.COMMTIMEOUT = 3.0  # segundos

log = comum.criar_log("cliente")

# Um proxy para cada replica. O proxy tem os mesmos metodos do objeto remoto,
# mas nao a logica: cada chamada e enviada ao controlador e o resultado volta.
controladores = {numero: Proxy(comum.uri_controlador(numero)) for numero in comum.REPLICAS}

# Replica que nao respondeu fica SUSPEITA por alguns segundos: as consultas a
# pulam. Sem isto, a espera pela replica caida separaria no tempo as chamadas
# as outras duas, e as respostas delas deixariam de coincidir.
SUSPEITA_DURA = 10.0  # segundos
suspeita_ate = {}     # numero da replica -> instante ate o qual ela e pulada

MENU = """
1. Ver painel
2. Acompanhar (Ctrl+C para voltar)
3. Ver ultimos eventos
4. Parar a linha
5. Rearmar a linha
6. Comparar as replicas
0. Sair
"""


def chamar_em_todas(metodo, *argumentos, tentativas=1, pular_suspeitas=False):
    """Chama o mesmo metodo nas tres replicas, uma depois da outra.
    Devolve {numero: resposta}; a replica que nao respondeu fica de fora."""
    respostas = {}
    for numero, proxy in controladores.items():
        if pular_suspeitas and time.monotonic() < suspeita_ate.get(numero, 0):
            continue
        for tentativa in range(1, tentativas + 1):
            # Os tres desfechos de uma chamada remota:
            try:
                respostas[numero] = getattr(proxy, metodo)(*argumentos)  # 1. devolveu o resultado
                break
            except CommunicationError as erro:                           # 3. nao veio resposta
                log.info("controlador-%s SEM RESPOSTA em %s, tentativa %d (%s)",
                         numero, metodo, tentativa, erro)
                suspeita_ate[numero] = time.monotonic() + SUSPEITA_DURA
            except Exception as erro:                                    # 2. o metodo deu erro la
                log.info("controlador-%s devolveu um erro em %s: %s", numero, metodo, erro)
                break
    return respostas


def votar(metodo, respostas):
    """Aceita a resposta dada por pelo menos duas replicas. Sem maioria, devolve None.
    A replica que respondeu diferente da maioria e apontada no log."""
    vencedora = comum.votar(list(respostas.values()))
    if vencedora is None:
        return None
    a_favor = [numero for numero, resposta in respostas.items() if resposta == vencedora]
    divergentes = [numero for numero, resposta in respostas.items() if resposta != vencedora]
    print(f"(maioria: {a_favor})")
    if divergentes:
        log.info("DIVERGENCIA em %s: controlador %s respondeu diferente da maioria %s",
                 metodo, divergentes, a_favor)
    return vencedora


def consultar(metodo, *argumentos):
    """Consulta com voto. Duas replicas corretas podem diferir por um instante
    (uma leitura a caminho); por isso, sem maioria, consulta mais uma vez."""
    for vez in (1, 2):
        respostas = chamar_em_todas(metodo, *argumentos, pular_suspeitas=True)
        resposta = votar(metodo, respostas)
        if resposta is not None:
            return resposta
        time.sleep(0.3)  # da tempo de as replicas tratarem a leitura que estava a caminho
    log.info("%s: SEM MAIORIA (responderam: %s). Nada foi aceito.", metodo, sorted(respostas))
    return None


def mostrar_painel(painel):
    print(time.strftime("--- %H:%M:%S UTC ---", time.gmtime()))
    for c in painel["cilindros"]:
        temperatura = "sem leitura" if c["temperatura"] is None else f"{c['temperatura']:6.1f} C"
        print(f"cadeira {c['cadeira']} {c['cilindro']:<8} {temperatura}  {c['estado']}")
    print("valvulas:", painel["valvulas"],
          "| alarme:", painel["alarme"],
          "| parada:", "SIM" if painel["parada"] else "nao")


def ver_painel():
    painel = consultar("obter_painel")
    if painel is not None:
        mostrar_painel(painel)


def acompanhar():
    """Tempo real por sondagem: uma consulta por segundo."""
    try:
        while True:
            ver_painel()
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def ver_eventos():
    """Sem voto: cada replica registra os eventos com a hora do seu relogio,
    entao os registros nunca sao identicos. Mostra o da primeira que responder."""
    respostas = chamar_em_todas("obter_eventos", 15)
    if respostas:
        numero = min(respostas)
        print(f"(registro local do controlador-{numero}, sem voto)")
        for instante, tipo, descricao in respostas[numero]:
            print(instante, tipo, descricao)


def enviar_acao(metodo):
    """Uma acao do operador: um identificador novo, o mesmo para as tres
    replicas e para as repeticoes. O resultado e o da maioria."""
    pedido = str(uuid.uuid4())
    respostas = chamar_em_todas(metodo, pedido, tentativas=2)
    resposta = votar(metodo, respostas)
    if resposta is not None:
        log.info("%s (pedido %s): %s", metodo, pedido[:8], resposta["mensagem"])
    else:
        log.info("%s (pedido %s): SEM MAIORIA (responderam: %s). "
                 "Nao foi possivel confirmar a acao.", metodo, pedido[:8], sorted(respostas))


def pedir_parada():
    enviar_acao("parar_linha")


def pedir_rearme():
    enviar_acao("rearmar")


def comparar():
    respostas = chamar_em_todas("obter_resumo")
    for numero, resumo in respostas.items():
        quantidades = [quantidade for cadeira, cilindro, quantidade in resumo["leituras"]]
        print(f"controlador-{numero}: leituras por sensor {quantidades} | parada: {resumo['parada']}")
    resumos = list(respostas.values())
    if len(resumos) == len(controladores) and all(resumo == resumos[0] for resumo in resumos):
        log.info("comparacao: as %d replicas estao IGUAIS", len(resumos))
    else:
        log.info("comparacao: replicas DIFERENTES ou ausentes (responderam: %s)", sorted(respostas))
        votar("obter_resumo", respostas)


OPCOES = {"1": ver_painel, "2": acompanhar, "3": ver_eventos,
          "4": pedir_parada, "5": pedir_rearme, "6": comparar}

while True:
    print(MENU)
    try:
        escolha = input("opcao: ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if escolha == "0":
        break
    if escolha not in OPCOES:
        print("opcao invalida")
        continue
    OPCOES[escolha]()
