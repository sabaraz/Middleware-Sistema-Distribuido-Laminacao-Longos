@echo off
rem ============================================================================
rem  MENU DA APRESENTACAO - Middleware de supervisao termica TANDEM
rem
rem  Uso: duplo clique. Esta janela fica aberta como painel de controle.
rem  Para ler este arquivo: opcao A do menu (abre no Bloco de Notas).
rem
rem  O QUE ESTE ARQUIVO FAZ
rem    - confere o ambiente (Docker, Python, bibliotecas) e corrige o que der;
rem    - monta cada cenario dos experimentos do relatorio, sempre limpo;
rem    - provoca e encerra a falha de refrigeracao;
rem    - derruba e traz de volta um controlador;
rem    - abre o MQTT Explorer (e instala, se faltar);
rem    - RESET TOTAL (opcao R): volta ao estado conhecido a partir de
rem      qualquer situacao.
rem
rem  O QUE ESTE ARQUIVO NAO FAZ (e feito por voce, na janela do cliente)
rem    - linha parada      = rearme pelo cliente.py, opcao 5;
rem    - parar a linha     = cliente.py, opcao 4;
rem    - ver o voto        = cliente.py, opcoes 1 e 2;
rem    - comparar replicas = cliente.py, opcao 6.
rem    O menu nunca publica comando em laminacao/#. So publica no topico de
rem    simulacao (a falha de refrigeracao).
rem
rem  ERROS QUE VOCE PODE COMETER SEGUINDO ESTE MENU (e a saida de cada um)
rem    1. Docker Desktop fechado.
rem         O menu tenta abrir e espera ate 2 minutos. Se nao subir, abra
rem         o Docker Desktop a mao e use a opcao R.
rem    2. Pedir o rearme (cliente, opcao 5) com a falha ainda ligada ou com
rem         o cilindro ainda quente. O controlador RECUSA: e o comportamento
rem         certo. Use N aqui, espere os seis cilindros em "normal" e peca de
rem         novo.
rem    3. Esquecer a falha ligada e trocar de experimento.
rem         Nao tem problema: todo cenario (3 a 7) e o R reiniciam o broker
rem         e os sensores, o que encerra a falha.
rem    4. Usar F duas vezes. Nao tem efeito: a falha ja esta ligada.
rem       F, N, D e V contam 5 segundos antes de agir: e de proposito, para
rem       voce trocar de janela. Nao aperte de novo achando que travou.
rem    5. Usar D (derrubar) num cenario com replica defeituosa.
rem         Sobram menos de duas replicas corretas e o cliente mostra
rem         SEM MAIORIA. E o limite do sistema, nao um defeito. Para voltar,
rem         escolha o cenario de novo.
rem    6. Usar V (voltar) num controlador que estava mentindo.
rem         Ele volta CORRETO. Para ter a replica defeituosa de novo, escolha
rem         o cenario de novo (4 a 7).
rem    7. Fechar a janela do cliente sem querer. Use C.
rem    8. Fechar a janela de um controlador ou do campo sem querer.
rem         Use S para ver o que esta no ar; V reabre um controlador; para o
rem         campo, escolha o cenario de novo.
rem    9. Fechar ESTA janela. Nada para: os processos continuam. Abra o
rem         arquivo de novo; para comecar do zero, opcao R.
rem   10. Dar ao MQTT Explorer um identificador de cliente igual ao de um
rem         processo (controlador-1, atuador-parada...). O broker derruba o
rem         processo verdadeiro. Deixe o identificador que o programa gera.
rem   11. Publicar pelo MQTT Explorer em laminacao/#. Conta como voto de
rem         replica. Publique so em simulacao/... (ou use F e N).
rem   12. Comparar as replicas (cliente, opcao 6) com os sensores rodando.
rem         Pode dar DIFERENTES por um instante: uma replica recebeu uma
rem         leitura a mais. Repita a opcao 6.
rem   13. Abrir este menu duas vezes. Os dois comandam os mesmos processos;
rem         use um so.
rem   14. Ter outro projeto Python aberto com arquivos de mesmo nome
rem         (sensor.py, cliente.py...). O menu fecha processos pelo nome do
rem         arquivo e fecharia esses tambem.
rem   15. Porta 1883 ocupada por outro broker (por exemplo um Mosquitto
rem         instalado como servico do Windows). O menu avisa e nao consegue
rem         resolver sozinho: pare o outro broker e use R.
rem   16. Sem internet na primeira vez. Baixar a imagem do broker, instalar
rem         as bibliotecas e instalar o MQTT Explorer precisam de rede. Faca
rem         as opcoes 1 e 2 ANTES do dia da apresentacao.
rem
rem  SE NADA DISSO RESOLVER: opcao R. Se o R falhar, siga o "Roteiro manual"
rem  do README.md, passo a passo.
rem
rem  NOTAS PARA QUEM ALTERAR ESTE ARQUIVO
rem    - Sem acentos: o console do Windows troca os caracteres.
rem    - Nao usar o sinal de "maior" dentro de echo: o cmd entende como
rem      redirecionamento para arquivo.
rem    - As esperas usam ping em vez de timeout, que falha quando a entrada
rem      nao e o teclado.
rem    - "docker compose exec" e "powershell" levam "<nul" no fim: sem isso
rem      eles engolem o que foi digitado para o menu.
rem ============================================================================

setlocal EnableExtensions
title TANDEM - Menu da apresentacao
cd /d "%~dp0"

set "TOPICO_FALHA=simulacao/cadeira/2/cilindro/superior/falha"
set "MQTT_EXPLORER=%LOCALAPPDATA%\Programs\MQTT-Explorer\MQTT Explorer.exe"
set "CENARIO=nenhum (use 3 a 7, ou R)"
set "FALHA=desligada"
set "VAZIAS=0"
rem Segundos de contagem antes de F, N, D e V: tempo de trocar para a janela
rem do cliente e ver a mudanca acontecer. Faixa util: 4 a 6.
set "CONTAGEM=5"

call :achar_python
if not defined PYTHON_EXE (
    echo.
    echo ERRO: Python nao foi encontrado.
    echo Instale o Python 3.11 ou mais novo e abra este arquivo de novo.
    pause
    exit /b 1
)

rem Uso sem menu, para uma acao so: iniciar_apresentacao.bat OPCAO [NUMERO]
rem Exemplos: "iniciar_apresentacao.bat 3", "iniciar_apresentacao.bat D 2".
set "UMA_VEZ="
set "NUM_ARG=%~2"
if not "%~1"=="" (
    set "OP=%~1"
    set "UMA_VEZ=1"
    goto despachar
)

rem ---------------------------------------------------------------- menu ----
:menu
cls
echo.
echo  ===== TANDEM - menu da apresentacao =====
echo  Cenario atual: %CENARIO%
echo  Falha de refrigeracao (cadeira 2, superior): %FALHA%
echo.
echo  PREPARAR
echo    1  Verificar o ambiente (Docker, Python, bibliotecas)
echo    2  Abrir / instalar o MQTT Explorer
echo.
echo  CENARIOS (cada um fecha tudo, limpa e abre de novo)
echo    3  Tres replicas corretas ............ E1, E2, E3, E4
echo    4  Controlador 2 mente sempre ........ E5
echo    5  Controlador 2 intermitente ........ E5
echo    6  Controladores 2 e 3 mentem ........ E6 caso 1
echo    7  Controlador 3 fora, 2 mente ....... E6 caso 2
echo.
echo  DURANTE O EXPERIMENTO
echo    F  Provocar a falha de refrigeracao    N  Encerrar a falha
echo    D  Derrubar um controlador (E3)        V  Trazer de volta (E4)
echo    C  Reabrir o cliente                   S  Ver o que esta no ar
echo    B  Ver o broker em texto
echo.
echo  SOCORRO
echo    R  RESET TOTAL (resolve qualquer estado e abre o cenario 3)
echo    A  Abrir este arquivo no Bloco de Notas (erros possiveis e saidas)
echo    0  Encerrar tudo e sair            Q  Sair sem fechar nada
echo.
echo  O MENU NAO FAZ - e na janela do cliente.py:
echo    linha parada = rearme: opcao 5 (antes: N aqui e cilindros em normal)
echo    parar a linha: opcao 4      acompanhar o voto: opcao 2
echo    comparar as replicas: opcao 6
echo.
set "OP="
set /p "OP=  Opcao: "
if not defined OP goto entrada_vazia
set "VAZIAS=0"
set "OP=%OP:"=%"
if not defined OP goto menu
set "OP=%OP: =%"
if not defined OP goto menu

:despachar
if "%OP%"=="1" goto op_verificar
if "%OP%"=="2" goto op_explorer
if "%OP%"=="3" goto op_cenario3
if "%OP%"=="4" goto op_cenario4
if "%OP%"=="5" goto op_cenario5
if "%OP%"=="6" goto op_cenario6
if "%OP%"=="7" goto op_cenario7
if /i "%OP%"=="F" goto op_falha_ligar
if /i "%OP%"=="N" goto op_falha_desligar
if /i "%OP%"=="D" goto op_derrubar
if /i "%OP%"=="V" goto op_voltar
if /i "%OP%"=="C" goto op_cliente
if /i "%OP%"=="S" goto op_estado
if /i "%OP%"=="B" goto op_broker_texto
if /i "%OP%"=="R" goto op_reset
if /i "%OP%"=="A" goto op_ler
if "%OP%"=="0" goto op_sair
if /i "%OP%"=="Q" exit /b 0
echo.
echo  Opcao invalida: %OP%
if defined UMA_VEZ exit /b 1
call :esperar 2
goto menu

rem Enter sozinho volta ao menu. Muitas vezes seguidas significa que nao ha
rem teclado ligado a esta janela: sai, em vez de girar para sempre.
:entrada_vazia
set /a VAZIAS+=1
if %VAZIAS% geq 30 exit /b 1
goto menu

rem ------------------------------------------------------------- opcoes ----
:op_verificar
echo.
call :verificar_ambiente
if errorlevel 1 (echo. & echo  RESULTADO: ha problema no ambiente. Leia as linhas acima.) else (echo. & echo  RESULTADO: ambiente pronto.)
goto voltar_ao_menu

:op_explorer
echo.
if exist "%MQTT_EXPLORER%" goto explorer_abrir
echo  O MQTT Explorer nao esta instalado em:
echo    %MQTT_EXPLORER%
echo.
echo  Instalacao pelo winget (baixa o instalador oficial; precisa de internet):
echo    winget install --id thomasnordquist.MQTT-Explorer -e
echo.
set "RESP="
set /p "RESP=  Instalar agora? (S/N): "
if /i not "%RESP%"=="S" goto explorer_site
winget install --id thomasnordquist.MQTT-Explorer -e
if exist "%MQTT_EXPLORER%" goto explorer_abrir
echo.
echo  A instalacao pelo winget nao deixou o programa no lugar esperado.
:explorer_site
echo  Abrindo a pagina oficial para baixar a mao: https://mqtt-explorer.com
start "" "https://mqtt-explorer.com"
goto voltar_ao_menu
:explorer_abrir
start "" "%MQTT_EXPLORER%"
echo  MQTT Explorer aberto. Na conexao:
echo    Host: localhost     Porta: 1883     sem usuario, sem senha, sem TLS
echo    Deixe o identificador de cliente que o programa gera.
echo    Expanda a arvore "laminacao".
echo  Somente observacao. Nao publique em laminacao/#.
goto voltar_ao_menu

:op_cenario3
call :montar_cenario correto correto correto
if errorlevel 1 goto voltar_ao_menu
set "CENARIO=3 - tres replicas corretas"
echo.
echo  ROTEIRO
echo   E1: no cliente, opcao 2. Seis cilindros em normal, maioria [1, 2, 3].
echo   E2: F aqui. Alerta em cerca de 2 s (valvula 2 em 100, alarme ligado);
echo       parada da linha cerca de 33 s depois. Entao: N aqui, esperar os
echo       cilindros em normal, e no cliente opcao 5 (rearme).
echo   E3: D aqui, controlador 2. No cliente, opcoes 1, 4 e 5: tudo aceito
echo       com maioria [1, 3]; cada acao demora cerca de 4 s.
echo   E4: V aqui, controlador 2. Na janela dele: "recuperacao: ... leituras
echo       recebidas". No cliente, opcao 6: replicas IGUAIS.
goto voltar_ao_menu

:op_cenario4
call :montar_cenario correto mentir correto
if errorlevel 1 goto voltar_ao_menu
set "CENARIO=4 - controlador 2 mente sempre"
echo.
echo  ROTEIRO (E5)
echo   No cliente, opcao 2: o controlador 2 aparece como divergente em toda
echo   consulta; o painel aceito e o verdadeiro, pela maioria [1, 3].
echo   F aqui: a valvula abre e a linha para pelo voto de 1 e 3.
echo   No MQTT Explorer: dois comandos em 100, um em 50, aplicado 100.
echo   Depois: N aqui, esperar normal, cliente opcao 5.
goto voltar_ao_menu

:op_cenario5
call :montar_cenario correto intermitente correto
if errorlevel 1 goto voltar_ao_menu
set "CENARIO=5 - controlador 2 intermitente"
echo.
echo  ROTEIRO (E5)
echo   O controlador 2 mente 5 s e acerta 5 s. No cliente, opcao 2: ele
echo   aparece como divergente so em parte das consultas.
echo   F aqui: a valvula abre e a linha para do mesmo jeito.
echo   Depois: N aqui, esperar normal, cliente opcao 5.
goto voltar_ao_menu

:op_cenario6
call :montar_cenario correto mentir mentir
if errorlevel 1 goto voltar_ao_menu
set "CENARIO=6 - controladores 2 e 3 mentem"
echo.
echo  ROTEIRO (E6 caso 1) - o limite do voto 2 de 3
echo   F aqui. A replica 1 detecta o critico (veja a janela dela), mas a
echo   linha NAO para e a valvula NAO abre. O cliente aceita o painel falso
echo   e aponta o controlador 1 como o divergente.
echo   A temperatura sobe ate o teto da simulacao (150 graus).
echo   Para sair deste cenario: escolha outro (3 a 7) ou R.
goto voltar_ao_menu

:op_cenario7
call :montar_cenario correto mentir fora
if errorlevel 1 goto voltar_ao_menu
set "CENARIO=7 - controlador 3 fora, 2 mente"
echo.
echo  ROTEIRO (E6 caso 2)
echo   No cliente, opcao 1: "SEM MAIORIA (responderam: [1, 2])".
echo   No cliente, opcao 4: o cliente recebe "linha parada", mas o atuador
echo   mantem 0 (veja a janela do campo: "sem maioria").
echo   Para sair deste cenario: escolha outro (3 a 7) ou R.
goto voltar_ao_menu

:op_falha_ligar
echo.
call :contar "ligar a falha de refrigeracao"
call :publicar_falha 1
if errorlevel 1 goto falha_erro
set "FALHA=LIGADA"
echo  Falha de refrigeracao LIGADA na cadeira 2, cilindro superior.
echo  Acompanhe no cliente, opcao 2.
echo  Quando terminar: N aqui, esperar os cilindros em normal, e so entao
echo  o rearme no cliente, opcao 5.
goto voltar_ao_menu

:op_falha_desligar
echo.
call :contar "encerrar a falha de refrigeracao"
call :publicar_falha 0
if errorlevel 1 goto falha_erro
set "FALHA=desligada"
echo  Falha de refrigeracao encerrada. O cilindro esfria em alguns segundos.
echo  Linha parada = rearme pelo cliente.py, opcao 5, com os seis cilindros
echo  em normal.
goto voltar_ao_menu

:falha_erro
echo  ERRO: nao consegui publicar no broker. Ele esta no ar?
echo  Use S para conferir. Se o broker estiver fora, use R.
goto voltar_ao_menu

:op_derrubar
echo.
call :perguntar_controlador
if errorlevel 1 goto voltar_ao_menu
call :contar "derrubar o controlador %NUM%"
call :matar "controlador\.py\W+%NUM%\b"
call :esperar 2
echo  Controlador %NUM% derrubado.
echo  No cliente: "controlador-%NUM% SEM RESPOSTA" e maioria das outras duas.
echo  Para trazer de volta: V.
goto voltar_ao_menu

:op_voltar
echo.
call :perguntar_controlador
if errorlevel 1 goto voltar_ao_menu
call :contar "trazer de volta o controlador %NUM%"
call :matar "controlador\.py\W+%NUM%\b"
call :esperar 2
call :abrir_controlador %NUM% correto
call :esperar_controlador %NUM%
echo  Na janela dele: "recuperacao: ... leituras recebidas de controlador-...".
echo  No cliente, opcao 6, para comparar as replicas.
goto voltar_ao_menu

:op_cliente
echo.
call :matar "cliente\.py"
call :esperar 1
call :abrir_cliente
echo  Cliente aberto em outra janela.
goto voltar_ao_menu

:op_estado
echo.
call :mostrar_estado
goto voltar_ao_menu

:op_broker_texto
echo.
start "TANDEM - Broker em texto" cmd /k "docker compose exec broker mosquitto_sub -v -t laminacao/#"
echo  Janela aberta com tudo o que passa em laminacao/#. Feche quando quiser.
goto voltar_ao_menu

:op_reset
echo.
echo  RESET TOTAL: fecha todos os processos, recria o broker, apaga a pasta
echo  "dados", confere o ambiente e abre o cenario 3.
echo.
call :matar_tudo
call :garantir_docker
if errorlevel 1 goto voltar_ao_menu
docker compose down --remove-orphans
docker rm -f laminacao-broker >nul 2>&1
call :verificar_ambiente
if errorlevel 1 (
    echo.
    echo  O RESET parou: ha problema no ambiente. Leia as linhas acima.
    echo  Se nao resolver, siga o "Roteiro manual" do README.md.
    goto voltar_ao_menu
)
goto op_cenario3

:op_ler
start "" notepad "%~f0"
if defined UMA_VEZ exit /b 0
goto menu

:op_sair
echo.
echo  Fechando os processos e o broker...
call :matar_tudo
docker compose down
echo  Encerrado.
call :esperar 2
endlocal
exit /b 0

:voltar_ao_menu
if defined UMA_VEZ exit /b 0
echo.
pause
goto menu

rem ====================================================== sub-rotinas =======

rem Acha o Python: primeiro o da pasta .venv, depois o do sistema.
:achar_python
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
) else (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
)
goto :eof

rem Espera N segundos (aproximado). Nao usa "timeout": ver notas no inicio.
:esperar
set /a PINGS=%~1+1
ping -n %PINGS% 127.0.0.1 >nul
goto :eof

rem Contagem antes de uma acao (%1 = o que vai acontecer). A acao so ocorre
rem quando a contagem termina: da tempo de trocar para a janela do cliente.
:contar
echo  Vou %~1 em %CONTAGEM% segundos.
echo  Troque agora para a janela do cliente (opcao 2) para ver a mudanca.
for /l %%S in (%CONTAGEM%,-1,1) do (
    <nul set /p "=  %%S..."
    ping -n 2 127.0.0.1 >nul
)
echo  agora.
goto :eof

rem Fecha os processos (python e a janela cmd que os abriu) cuja linha de
rem comando casa com a expressao recebida. Nao depende do titulo da janela.
:matar
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'cmd.exe') -and $_.CommandLine -match '%~1' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" <nul
goto :eof

:matar_tudo
call :matar "(controlador|iniciar_campo|iniciar_controladores|sensor|atuador|cliente)\.py"
call :matar "mosquitto_sub"
call :esperar 2
goto :eof

rem Garante o Docker respondendo. Se estiver fechado, tenta abrir o Docker
rem Desktop e espera ate cerca de 2 minutos.
:garantir_docker
docker info >nul 2>&1
if not errorlevel 1 goto :eof
where docker >nul 2>&1
if errorlevel 1 (
    echo  ERRO: o comando "docker" nao existe. Instale o Docker Desktop.
    exit /b 1
)
echo  O Docker nao esta respondendo. Tentando abrir o Docker Desktop...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set "TENTATIVA=0"
:garantir_docker_espera
call :esperar 5
docker info >nul 2>&1
if not errorlevel 1 goto garantir_docker_ok
set /a TENTATIVA+=1
if %TENTATIVA% lss 24 goto garantir_docker_espera
echo  ERRO: o Docker nao respondeu em 2 minutos.
echo  Abra o Docker Desktop a mao, espere ficar pronto e use a opcao R.
exit /b 1
:garantir_docker_ok
echo  Docker pronto.
exit /b 0

rem Sobe o broker e espera ele aceitar conexao.
:subir_broker
docker compose up -d
if errorlevel 1 (
    echo  ERRO: o broker nao subiu. Causas comuns: porta 1883 ocupada por
    echo  outro broker, ou sem internet para baixar a imagem na primeira vez.
    exit /b 1
)
set "TENTATIVA=0"
:subir_broker_espera
docker compose exec -T broker mosquitto_pub -t menu/pronto -m 1 <nul >nul 2>&1
if not errorlevel 1 exit /b 0
set /a TENTATIVA+=1
if %TENTATIVA% geq 15 (
    echo  ERRO: o broker subiu mas nao aceita conexao.
    exit /b 1
)
call :esperar 1
goto subir_broker_espera

rem Confere Docker, broker e bibliotecas. Instala as bibliotecas se faltarem.
:verificar_ambiente
echo  [1/3] Docker...
call :garantir_docker
if errorlevel 1 exit /b 1
echo        ok
echo  [2/3] Broker MQTT...
call :subir_broker
if errorlevel 1 exit /b 1
echo        ok, em localhost:1883
echo  [3/3] Python e bibliotecas...
echo        %PYTHON_EXE%
"%PYTHON_EXE%" -c "import paho.mqtt.client, Pyro5.api" >nul 2>&1
if not errorlevel 1 goto verificar_ok
echo        Faltam bibliotecas. Instalando (precisa de internet)...
if not exist ".venv\Scripts\python.exe" "%PYTHON_EXE%" -m venv .venv
call :achar_python
"%PYTHON_EXE%" -m pip install -r requirements.txt
"%PYTHON_EXE%" -c "import paho.mqtt.client, Pyro5.api" >nul 2>&1
if errorlevel 1 (
    echo  ERRO: nao consegui instalar as bibliotecas. Sem internet?
    exit /b 1
)
:verificar_ok
echo        ok
if exist "%MQTT_EXPLORER%" (echo  MQTT Explorer: instalado. Opcao 2 abre.) else (echo  MQTT Explorer: NAO instalado. Opcao 2 instala.)
exit /b 0

rem Apaga a pasta "dados". Tenta varias vezes: logo depois de fechar um
rem controlador o Windows ainda segura o arquivo do banco por um instante.
:apagar_dados
set "TENTATIVA=0"
:apagar_dados_laco
if not exist dados goto :eof
rmdir /s /q dados 2>nul
if not exist dados goto :eof
set /a TENTATIVA+=1
if %TENTATIVA% geq 10 (
    echo  AVISO: nao consegui apagar a pasta "dados". Algum controlador ainda
    echo  esta aberto. Feche as janelas dele e use a opcao R.
    exit /b 1
)
call :esperar 1
goto apagar_dados_laco

rem Monta um cenario limpo. Parametros: o modo de cada controlador, na
rem ordem 1 2 3. Modos: correto, mentir, intermitente, fora.
:montar_cenario
echo.
echo  [1/5] Fechando o que estiver aberto...
call :matar_tudo
echo  [2/5] Docker e broker (reinicio, para nao sobrar mensagem retida)...
call :garantir_docker
if errorlevel 1 exit /b 1
call :subir_broker
if errorlevel 1 exit /b 1
docker compose restart broker >nul 2>&1
call :subir_broker
if errorlevel 1 exit /b 1
set "FALHA=desligada"
echo  [3/5] Apagando a pasta "dados"...
call :apagar_dados
if errorlevel 1 exit /b 1
echo  [4/5] Abrindo os controladores...
call :abrir_controlador 1 %~1
call :abrir_controlador 2 %~2
call :abrir_controlador 3 %~3
set "FALTOU="
if /i not "%~1"=="fora" call :esperar_controlador 1
if /i not "%~2"=="fora" call :esperar_controlador 2
if /i not "%~3"=="fora" call :esperar_controlador 3
echo  [5/5] Abrindo o campo (6 sensores, 5 atuadores) e o cliente...
start "TANDEM - Campo (sensores e atuadores)" cmd /k ""%PYTHON_EXE%" iniciar_campo.py"
call :esperar 3
call :abrir_cliente
if defined FALTOU (
    echo.
    echo  ATENCAO: algum controlador nao respondeu. Veja a janela dele.
    echo  Se o erro for de endereco em uso, use a opcao R.
    exit /b 1
)
echo.
echo  Cenario pronto.
exit /b 0

rem Abre um controlador em janela propria. %1 = numero, %2 = modo.
:abrir_controlador
if /i "%~2"=="fora" (
    echo        controlador %~1: NAO iniciado, de proposito
    goto :eof
)
set "MODO=%~2"
if /i "%MODO%"=="correto" set "MODO="
start "TANDEM - Controlador %~1 %MODO%" cmd /k ""%PYTHON_EXE%" controlador.py %~1 %MODO%"
goto :eof

rem Espera o controlador %1 aceitar conexao na porta dele (9090 + numero).
rem Testa IPv6 e IPv4: o controlador escuta em "localhost", que no Windows
rem costuma ser o endereco IPv6 (::1).
:esperar_controlador
"%PYTHON_EXE%" -c "import socket,sys,time; p=9090+int(sys.argv[1]); no_ar=lambda: any(socket.socket(f).connect_ex((h,p))==0 for f,h in ((socket.AF_INET6,'::1'),(socket.AF_INET,'127.0.0.1'))); sys.exit(0 if any(no_ar() or time.sleep(0.5) for i in range(12)) else 1)" %~1
if errorlevel 1 (
    echo        controlador %~1: NAO RESPONDEU
    set "FALTOU=1"
) else (
    echo        controlador %~1: no ar
)
goto :eof

:abrir_cliente
start "TANDEM - Cliente do operador" cmd /k ""%PYTHON_EXE%" cliente.py"
goto :eof

rem Liga (1) ou desliga (0) a falha de refrigeracao na simulacao.
:publicar_falha
docker compose exec -T broker mosquitto_pub -q 1 -t %TOPICO_FALHA% -m %~1 <nul
exit /b %errorlevel%

rem Pergunta o numero do controlador. Enter sozinho = 2.
:perguntar_controlador
set "NUM=2"
if defined NUM_ARG set "NUM=%NUM_ARG%"
if not defined UMA_VEZ set /p "NUM=  Qual controlador? (1, 2 ou 3; Enter = 2): "
set "NUM=%NUM:"=%"
if "%NUM%"=="1" exit /b 0
if "%NUM%"=="2" exit /b 0
if "%NUM%"=="3" exit /b 0
echo  Numero invalido. Nada foi feito.
exit /b 1

:mostrar_estado
docker compose exec -T broker mosquitto_pub -t menu/pronto -m 1 <nul >nul 2>&1
if errorlevel 1 (echo   broker MQTT ......... FORA) else (echo   broker MQTT ......... no ar)
"%PYTHON_EXE%" -c "import socket; no_ar=lambda p: any(socket.socket(f).connect_ex((h,p))==0 for f,h in ((socket.AF_INET6,'::1'),(socket.AF_INET,'127.0.0.1'))); [print('  controlador', n, '.......', 'no ar' if no_ar(9090+n) else 'FORA') for n in (1, 2, 3)]"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\"; $s = @($p | Where-Object { $_.CommandLine -match 'sensor\.py' }).Count; $a = @($p | Where-Object { $_.CommandLine -match 'atuador\.py' }).Count; $c = @($p | Where-Object { $_.CommandLine -match 'cliente\.py' }).Count; if ($s -gt 0 -and $a -gt 0) { '  campo ............... no ar' } else { '  campo ............... FORA' }; if ($c -gt 0) { '  cliente ............. no ar' } else { '  cliente ............. FORA' }" <nul
echo.
echo   Cenario atual: %CENARIO%
echo   Falha de refrigeracao: %FALHA%
goto :eof
