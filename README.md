# Middleware para supervisão térmica de cilindros na laminação TANDEM de tarugos e beam blanks

1º Trabalho Prático de Sistemas Distribuídos.

Sensores de temperatura dos cilindros de um grupo TANDEM de três cadeiras de
laminação a quente de blocos de aço (tarugos, beam blanks e outros
semiacabados para produtos longos) publicam leituras; três controladores replicados decidem; atuadores
(válvulas de refrigeração, alarme e parada da linha) executam o que a maioria
comandar; um cliente de terminal acompanha e age.

Inspirado na laminação de perfis estruturais da Gerdau Ouro Branco. Tudo é
simulado; nenhum dado da empresa é usado.

A Documentação do Trabalho se encontra em [docs/relatorio.pdf](docs/relatorio.pdf).

## Requisitos

- Python 3.11 ou mais novo (testado com 3.11.9 e 3.14.6)
- Docker com Docker Compose

## Preparação

```
pip install -r requirements.txt
docker compose up -d
```

## Execução

Um terminal para cada comando, com o ambiente virtual ativado:

```
python iniciar_controladores.py
python iniciar_campo.py
python cliente.py
```

## Demonstrações

| O que mostrar | Como |
|---|---|
| Falha de refrigeração em um cilindro | `docker compose exec broker mosquitto_pub -q 1 -t simulacao/cadeira/2/cilindro/superior/falha -m 1` |
| Encerrar a falha | O mesmo comando com `-m 0` |
| Queda de um controlador | Encerrar o processo; trazer de volta com `python controlador.py 2` |
| Controlador que mente sempre | `python controlador.py 2 mentir` |
| Controlador com erro intermitente | `python controlador.py 2 intermitente` |
| Comandos circulando no broker | `docker compose exec broker mosquitto_sub -v -t "laminacao/#"` |
| O mesmo, em árvore (opcional) | MQTT Explorer ligado a `localhost:1883`; ver a seção 5.4 do relatório |
| Partir sem resíduo | `docker compose restart broker` e apagar a pasta `dados` |

Para usar um controlador defeituoso, inicie as três réplicas uma a uma
(`python controlador.py 1`, `python controlador.py 2 mentir`,
`python controlador.py 3`) em vez de `iniciar_controladores.py`.

## Arquivos

| Arquivo | Papel |
|---|---|
| `comum.py` | Tópicos, endereços, voto, validação das mensagens, log e conexão com o broker |
| `sensor.py` | Sensor simulado de um cilindro |
| `atuador.py` | Atuador simulado; aplica o valor da maioria |
| `controlador.py` | Réplica do controlador: decide, comanda e atende o cliente |
| `armazenamento.py` | Armazenamento de uma réplica (SQLite) |
| `cliente.py` | Cliente do operador |
| `iniciar_campo.py` | Inicia os 6 sensores e os 5 atuadores |
| `iniciar_controladores.py` | Inicia as 3 réplicas |
| `docker-compose.yml`, `mosquitto/` | Broker MQTT |
| `experimentos/` | Logs das execuções citadas no relatório |
| `docs/` | Relatório e imagens |

Ao executar, os programas criam a pasta `logs/` (um arquivo por processo; as
leituras dos sensores ficam só nela, não na tela) e a pasta `dados/` (um banco
por réplica).
