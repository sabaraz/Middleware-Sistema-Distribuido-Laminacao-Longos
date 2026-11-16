# Middleware para supervisão térmica de cilindros na laminação TANDEM de tarugos e beam blanks

1º Trabalho Prático de Sistemas Distribuídos.

A documentação completa do trabalho está em [docs/relatorio.pdf](docs/relatorio.pdf).
Este arquivo é o guia de execução.

## Inspiração do projeto

A ideia veio de duas leituras:

- [Catálogo Gerdau de perfis estruturais](https://api.aecweb.com.br/cls/catalogos/28792/22314/catalogo-gerdau-perfis-estruturais.pdf):
  o produto. Perfis estruturais são laminados a quente em cadeiras em
  sequência, a partir de blocos de aço como tarugos e beam blanks. Daí o
  cenário de um grupo TANDEM de três cadeiras, cada uma com um cilindro
  superior e um inferior.
- [Fire crack failure of a ductile cast iron roll](https://ph01.tci-thaijo.org/index.php/kbej/article/view/147773)
  (Boonrampai e Netpu, Kasem Bundit Engineering Journal, v. 8, n. 3, 2018):
  o problema. O artigo analisa um cilindro de laminação a quente que falhou
  com 3.500 toneladas de serviço, quando o normal era de 65.000 a 70.000, por
  trincas térmicas causadas por refrigeração insuficiente. Daí a pergunta do
  trabalho: perceber cedo que um cilindro está aquecendo, abrir a
  refrigeração e, no limite, parar a linha.

Tudo é simulado. Nenhum dado de empresa é usado.

## O que o sistema faz

Seis sensores de temperatura (um por cilindro) publicam leituras por MQTT.
Três controladores replicados recebem as mesmas leituras e decidem. Cinco
atuadores (três válvulas de refrigeração, o alarme e a parada da linha)
executam o que a maioria dos controladores comandar. Um cliente de terminal
consulta os três controladores por Pyro5 e aceita a resposta da maioria.

## Requisitos

- Windows com Python 3.11 ou mais novo (testado com 3.11.9 e 3.14.6)
- Docker Desktop, com Docker Compose
- Opcional: MQTT Explorer, para ver o broker em árvore

## Preparação (uma vez)

No terminal, dentro da pasta do projeto:

```
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Início rápido

Dê duplo clique em `iniciar_apresentacao.bat`. Ele abre um menu que fica na
tela como painel de controle:

| Opção | O que faz |
|---|---|
| 1 | Confere Docker, broker e bibliotecas; abre o Docker Desktop e instala as bibliotecas se faltarem |
| 2 | Abre o MQTT Explorer; se não estiver instalado, oferece a instalação |
| 3 a 7 | Monta um cenário dos experimentos: fecha tudo, reinicia o broker, apaga `dados` e abre os controladores no modo certo, o campo e o cliente |
| F, N | Provoca e encerra a falha de refrigeração |
| D, V | Derruba um controlador e o traz de volta |
| C, S, B | Reabre o cliente; mostra o que está no ar; mostra o broker em texto |
| R | Reset total: volta ao cenário 3 a partir de qualquer estado |
| A | Abre o próprio `.bat` no Bloco de Notas: lá estão os erros possíveis e a saída de cada um |
| 0, Q | Encerra tudo e sai; sai sem fechar nada |

Depois de montar um cenário, o menu mostra o que fazer e o que se espera ver.

O menu não opera o cliente. Na janela do `cliente.py`: linha parada = rearme
pela opção 5 (com a falha encerrada e os seis cilindros em normal); parar a
linha, opção 4; acompanhar o voto, opção 2; comparar as réplicas, opção 6.

Se algo sair do esperado, use a opção R. Se o R falhar, ou se o `.bat` não
abrir, siga o roteiro manual abaixo, sem pular passos.

## Roteiro manual

Faz o mesmo que o cenário 3 do `.bat`, um passo por vez. Cada passo tem uma conferência:
só avance quando ela passar. Todos os comandos são dados dentro da pasta do
projeto.

| Passo | Terminal | Comando | Conferência |
|---|---|---|---|
| 1 | qualquer | `docker compose up -d` | `docker compose ps` mostra `laminacao-broker` em execução |
| 2 | A | `.venv\Scripts\python.exe controlador.py 1` | Aparece "objeto remoto disponivel em PYRO:controlador@localhost:9091" |
| 3 | B | `.venv\Scripts\python.exe controlador.py 2` | O mesmo, com a porta 9092 |
| 4 | C | `.venv\Scripts\python.exe controlador.py 3` | O mesmo, com a porta 9093 |
| 5 | D | `.venv\Scripts\python.exe iniciar_campo.py` | Aparece "11 processos iniciados" |
| 6 | E | `.venv\Scripts\python.exe cliente.py` | Aparece o menu; a opção 1 mostra os seis cilindros com "(maioria: [1, 2, 3])" |

A ordem importa: broker, controladores, campo, cliente. Use o Windows
Terminal para o cliente; no console antigo os ícones do painel podem não
aparecer.

Opções do cliente: 1 ver painel; 2 acompanhar (Ctrl+C volta ao menu);
3 últimos eventos; 4 parar a linha; 5 rearmar; 6 comparar as réplicas;
0 sair.

### Se um passo falhar

| O que aparece | O que fazer |
|---|---|
| `docker` não é reconhecido, ou erro ao ligar ao Docker | Abrir o Docker Desktop, esperar ficar pronto e repetir o passo 1 |
| Porta 1883 em uso | Outro broker está ligado. Encerrar o outro e repetir o passo 1 |
| `.venv\Scripts\python.exe` não encontrado | Refazer a seção Preparação |
| `ModuleNotFoundError` (paho ou Pyro5) | `.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| Controlador encerra com erro de endereço em uso | Há outro controlador com o mesmo número aberto. Fechar a janela antiga e repetir o passo |
| Cliente mostra "SEM RESPOSTA" ou "SEM MAIORIA" logo no início | Conferir se as três janelas de controlador estão abertas; reabrir a que faltar |
| Linha já parada, alarme ligado ou cilindro em alerta logo ao iniciar | Sobrou estado de uma execução anterior. Fazer a partida limpa |

### Partida limpa

Use antes da apresentação e sempre que o sistema começar com resíduo.

1. Fechar as janelas do cliente, do campo e dos três controladores.
2. `docker compose restart broker`
3. `rmdir /s /q dados` (no PowerShell: `Remove-Item -Recurse -Force dados`)
4. Repetir o roteiro manual a partir do passo 2.

No menu, os cenários 3 a 7 e a opção R já fazem a partida limpa.

### Encerrar

Fechar as janelas dos processos e executar `docker compose down`.

## MQTT Explorer: visualização do broker

O MQTT Explorer é só um observador. O cliente de terminal continua sendo o
único caminho para parar ou rearmar a linha.

1. Com o sistema já iniciado, crie uma conexão.
2. Informe host `localhost` e porta `1883`.
3. Não informe usuário nem senha: o broker de simulação é local e anônimo.
4. Deixe o identificador de cliente que o programa gera. Um nome igual ao de
   um processo do sistema (`controlador-1`, `atuador-parada`) faz o broker
   derrubar esse processo.
5. Expanda a árvore `laminacao`: `cadeira` mostra sensores, comandos de
   refrigeração e valores aplicados; `linha` mostra alarme e parada.

Só o tópico de simulação pode receber publicação manual (ver a tabela
abaixo). Nunca publique em `laminacao/#`: um comando bem formado publicado à
mão conta como voto.

## Demonstrações

Comandos usados nas demonstrações, para quando o menu não estiver em uso:

| Ação | Comando |
|---|---|
| Provocar falha de refrigeração | `docker compose exec broker mosquitto_pub -q 1 -t simulacao/cadeira/2/cilindro/superior/falha -m 1` |
| Encerrar a falha | O mesmo comando com `-m 0` |
| Derrubar um controlador | Fechar a janela dele (ou Ctrl+C) |
| Trazer o controlador de volta | `.venv\Scripts\python.exe controlador.py 2` |
| Controlador que mente sempre | `.venv\Scripts\python.exe controlador.py 2 mentir` |
| Controlador com erro intermitente | `.venv\Scripts\python.exe controlador.py 2 intermitente` |
| Ver os comandos no broker, em texto | `docker compose exec broker mosquitto_sub -v -t "laminacao/#"` |

Pelo MQTT Explorer, a falha é provocada publicando o texto `1` em
`simulacao/cadeira/2/cilindro/superior/falha`, sem retenção; `0` encerra.

Roteiro de cada experimento do relatório (seção 6). Os tempos são os das
execuções locais registradas no relatório e variam um pouco a cada vez.

| Experimento | Como fazer | O que se espera ver |
|---|---|---|
| E1. Operação normal | Cenário 3; cliente, opção 2 | Seis cilindros em normal, "(maioria: [1, 2, 3])" |
| E2. Aquecimento de um cilindro | Provocar a falha; acompanhar pela opção 2; depois da parada, encerrar a falha e rearmar (opção 5) | Alerta em cerca de 2 s, com válvula 2 em 100 e alarme ligado; parada cerca de 33 s depois do alerta; rearme aceito depois que o cilindro esfria |
| E3. Queda de uma réplica | Fechar o controlador 2; usar as opções 1, 4 e 5 | "controlador-2 SEM RESPOSTA"; tudo aceito com maioria [1, 3]; a ação demora cerca de 4 s |
| E4. Réplica que reinicia | Abrir de novo o controlador 2; opção 6 | Na janela dele, "recuperacao: ... leituras recebidas"; no cliente, réplicas IGUAIS quando os sensores estão parados |
| E5. Réplica com valores errados | Cenário 4 ou 5 (manual: partida limpa e controlador 2 em `mentir` ou `intermitente`); provocar a falha | Cliente aponta o controlador 2 como divergente; válvula e parada aplicadas pelo voto de 1 e 3 |
| E6, caso 1. Duas réplicas mentindo | Cenário 6 (manual: partida limpa e controladores 2 e 3 em `mentir`); provocar a falha | A linha não pára e o painel aceito é o falso: limite do voto 2 de 3 |
| E6, caso 2. Uma fora e uma mentindo | Cenário 7 (manual: partida limpa; controlador 1 normal, 2 em `mentir`, 3 não iniciado) | Consultas com "SEM MAIORIA"; a parada pedida é confirmada ao cliente, mas o atuador mantém 0 |

Para usar um controlador defeituoso, feche a janela do controlador
correspondente e abra outra com o comando da tabela de ações. Os logs das
execuções citadas no relatório, inclusive a verificação de mensagem
malformada, estão em `experimentos/`.

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
| `iniciar_controladores.py` | Inicia as 3 réplicas numa só janela |
| `iniciar_apresentacao.bat` | Menu da apresentação no Windows: ambiente, cenários, falha e reset |
| `docker-compose.yml`, `mosquitto/` | Broker MQTT |
| `experimentos/` | Logs das execuções citadas no relatório |
| `docs/` | Relatório e imagens |

Ao executar, os programas criam a pasta `logs/` (um arquivo por processo; as
leituras dos sensores ficam só nela, não na tela) e a pasta `dados/` (um banco
por réplica).
