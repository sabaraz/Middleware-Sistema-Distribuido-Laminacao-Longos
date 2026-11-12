"""Memoria longa do controlador: um arquivo SQLite com leituras e eventos.

Gravar aqui significa ACRESCENTAR uma linha a uma tabela.
Nada e substituido: o historico so cresce.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone


class Armazenamento: # uso de classe pois haverão 3 controladores, 3 tabelas e 'armazenamentos' com caminhos diferentes
    def __init__(self, caminho):
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        # O banco e usado por duas threads (leituras e chamadas do cliente).
        # O controlador garante, com um mutex, que so uma o usa por vez;
        # por isso a verificacao do proprio sqlite3 pode ser desligada.
        self.banco = sqlite3.connect(caminho, check_same_thread=False)
        self.banco.execute(
            "CREATE TABLE IF NOT EXISTS leituras ("
            "cadeira INTEGER, cilindro TEXT, seq INTEGER, instante TEXT, temperatura REAL, "
            # Identidade da leitura: a mesma leitura nunca e gravada duas vezes.
            "PRIMARY KEY (cadeira, cilindro, instante))"
        )
        self.banco.execute(
            "CREATE TABLE IF NOT EXISTS eventos ("
            "instante TEXT, tipo TEXT, descricao TEXT)"
        )
        # Unica tabela em que um valor SUBSTITUI o anterior: guarda o que o
        # controlador precisa lembrar depois de cair e voltar.
        self.banco.execute(
            "CREATE TABLE IF NOT EXISTS persistente (chave TEXT PRIMARY KEY, valor TEXT)"
        )
        # Acoes do operador ja executadas: identificador do pedido e resposta dada.
        self.banco.execute(
            "CREATE TABLE IF NOT EXISTS pedidos (identificador TEXT PRIMARY KEY, resposta TEXT)"
        )
        self.banco.commit()

    def gravar_persistente(self, chave, valor):
        self.banco.execute("INSERT OR REPLACE INTO persistente VALUES (?, ?)", (chave, valor))
        self.banco.commit()

    def ler_persistente(self, chave, padrao):
        linha = self.banco.execute("SELECT valor FROM persistente WHERE chave = ?", (chave,)).fetchone()
        return linha[0] if linha else padrao

    def gravar_leitura(self, leitura):
        self.banco.execute(
            # OR IGNORE: se a leitura ja existe (veio do broker e da colega), nada muda.
            "INSERT OR IGNORE INTO leituras VALUES (?, ?, ?, ?, ?)",
            (leitura["cadeira"], leitura["cilindro"], leitura["seq"],
             leitura["instante"], leitura["temperatura"]),
        )
        self.banco.commit()  # so depois do commit a linha esta segura no disco

    def gravar_evento(self, tipo, descricao):
        instante = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.banco.execute("INSERT INTO eventos VALUES (?, ?, ?)", (instante, tipo, descricao))
        self.banco.commit()

    def ler_eventos(self, quantidade):
        """Os ultimos eventos, do mais antigo para o mais novo."""
        linhas = self.banco.execute(
            "SELECT instante, tipo, descricao FROM eventos ORDER BY rowid DESC LIMIT ?",
            (quantidade,),
        ).fetchall()
        return [list(linha) for linha in reversed(linhas)]

    def ultimo_instante(self):
        """Instante da leitura mais nova gravada ("" se nao ha nenhuma)."""
        return self.banco.execute("SELECT MAX(instante) FROM leituras").fetchone()[0] or ""

    def ler_leituras_desde(self, instante):
        """Leituras posteriores ao instante dado, no mesmo formato em que chegam do sensor."""
        linhas = self.banco.execute(
            "SELECT cadeira, cilindro, seq, instante, temperatura FROM leituras WHERE instante > ?",
            (instante,),
        ).fetchall()
        campos = ("cadeira", "cilindro", "seq", "instante", "temperatura")
        return [dict(zip(campos, linha)) for linha in linhas]

    def ler_resumo(self):
        """Quantidade de leituras de cada sensor: [[cadeira, cilindro, quantidade], ...]."""
        linhas = self.banco.execute(
            "SELECT cadeira, cilindro, COUNT(*) FROM leituras "
            "GROUP BY cadeira, cilindro ORDER BY cadeira, cilindro"
        ).fetchall()
        return [list(linha) for linha in linhas]

    def gravar_pedido(self, identificador, resposta):
        """Guarda a resposta dada a um pedido (um dicionario, gravado como texto JSON)."""
        self.banco.execute("INSERT OR IGNORE INTO pedidos VALUES (?, ?)",
                           (identificador, json.dumps(resposta)))
        self.banco.commit()

    def ler_pedido(self, identificador):
        """A resposta guardada para o pedido, ou None se ele nunca foi executado."""
        linha = self.banco.execute(
            "SELECT resposta FROM pedidos WHERE identificador = ?", (identificador,)
        ).fetchone()
        return json.loads(linha[0]) if linha else None

    def ler_pedidos(self):
        """Todos os pedidos executados: [[identificador, resposta], ...]."""
        linhas = self.banco.execute("SELECT identificador, resposta FROM pedidos").fetchall()
        return [[identificador, json.loads(resposta)] for identificador, resposta in linhas]
