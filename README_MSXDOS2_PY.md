# MSXDOS2.SYS 2.40 - reimplementação Python

Esta é uma reimplementação comportamental, em Python, do componente `MSXDOS2.SYS 2.40 (Silent)` de NYYRIKKI analisado a partir do binário fornecido.

Ela não é binariamente compatível com Z80 e não substitui `MSXDOS2.SYS` dentro de um MSX real. O arquivo original usa BIOS, BDOS, Memory Mapper e estruturas internas do MSX-DOS 2 que não existem no runtime Python.

## Comportamentos implementados

- drives virtuais `A:` a `Z:` mapeados para diretórios do computador host
- procura de `COMMAND2.COM`
- fallback para drive alternativo quando `COMMAND2.COM` não está disponível
- execução de `AUTOEXEC.BAT`
- suporte a `REBOOT.BAT`
- entrada de compatibilidade para BASIC e detecção de `AUTOEXEC.BAS`
- shell no estilo MSX-DOS com comandos básicos
- execução simples de arquivos `.BAT`
- isolamento do filesystem para impedir que caminhos escapem da raiz de cada drive virtual

## Comandos

`VER`, `DIR`, `TYPE`, `CD`, `COPY`, `DEL`, `REN`, `MD`, `RD`, `ECHO`, `SET`, `PATH`, `CLS`, `BASIC`, `REBOOT`, `HELP`, `EXIT`.

## Uso rápido

Crie um diretório que represente o drive A:

```bash
mkdir diskA
touch diskA/COMMAND2.COM
python msxdos2_py.py --drive A=./diskA
```

Mapeando dois drives:

```bash
python msxdos2_py.py --drive A=./diskA --drive B=./diskB --boot A
```

Boot direto para a camada BASIC:

```bash
python msxdos2_py.py --drive A=./diskA --basic
```

## AUTOEXEC.BAT de exemplo

```bat
ECHO MSX-DOS 2 Python iniciado
VER
DIR
```

## Limite de compatibilidade

O `MSXDOS2.SYS` original é um componente de inicialização e integração do MSX-DOS 2 com código Z80. Uma equivalência de baixo nível exigiria implementar ou emular:

1. Z80 e seu espaço de memória
2. BIOS/MSX slots
3. BDOS/MSX-DOS kernel calls
4. Memory Mapper
5. FAT12/FAT16 e drivers de disco do MSX
6. hooks e estruturas internas do DOS 2
7. carregamento real de `COMMAND2.COM` como código Z80

A versão Python criada aqui reproduz a camada de comportamento operacional em um sistema moderno, que é a abordagem adequada para portar a lógica para Python.
