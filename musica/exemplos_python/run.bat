@echo off
REM ====================================================================
REM  run.bat - Menu para executar os exemplos do Curso de Musica (MSX)
REM  Basta dar duplo-clique neste arquivo (ou rodar 'run' no terminal).
REM ====================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM Descobre qual comando de Python usar (python ou py).
set "PY=python"
where python >nul 2>nul || set "PY=py"

:menu
cls
echo ====================================================================
echo            CURSO DE MUSICA (MSX)  -  Exemplos em Python
echo ====================================================================
echo.
echo   1 - Altura (grave/medio/agudo, oitavas, cifras)      [Aula 2]
echo   2 - Duracao (figuras, ponto, pausas, andamento)      [Aula 3]
echo   3 - Escalas e modos gregos                           [Aula 5]
echo   4 - Acidentes (sustenido, bemol, temperamento)       [Aula 6]
echo   5 - Transposicao da cantiga do pastorzinho           [Aula 5]
echo   6 - Musica completa: Parabens pra Voce               [Ex. 6.8]
echo.
echo   D - Demonstracao rapida (escala da biblioteca base)
echo   T - Tocar TODOS os exemplos, em sequencia
echo   S - Sair
echo.
set "op="
set /p "op=Escolha uma opcao e tecle ENTER: "

if /i "%op%"=="1" call :run 01_altura.py
if /i "%op%"=="2" call :run 02_duracao.py
if /i "%op%"=="3" call :run 03_escalas.py
if /i "%op%"=="4" call :run 04_acidentes.py
if /i "%op%"=="5" call :run 05_transposicao.py
if /i "%op%"=="6" call :run 06_musica_completa.py
if /i "%op%"=="D" call :run msx_music.py
if /i "%op%"=="T" goto todos
if /i "%op%"=="S" goto fim

goto menu

:todos
cls
echo Tocando TODOS os exemplos em sequencia...
echo.
for %%F in (01_altura.py 02_duracao.py 03_escalas.py 04_acidentes.py 05_transposicao.py 06_musica_completa.py) do (
    echo --------------------------------------------------------------
    echo  %%F
    echo --------------------------------------------------------------
    "%PY%" "%%F"
    echo.
)
echo Fim de todos os exemplos.
pause
goto menu

REM --- sub-rotina que roda um exemplo e espera uma tecla -------------
:run
cls
echo --------------------------------------------------------------
echo  Executando: %~1
echo --------------------------------------------------------------
echo.
"%PY%" "%~1"
echo.
echo --------------------------------------------------------------
pause
goto menu

:fim
endlocal
