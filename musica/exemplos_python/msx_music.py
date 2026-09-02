# -*- coding: utf-8 -*-
"""
msx_music.py  -  Mini "comando PLAY" do MSX em Python
=====================================================

Esta biblioteca recria, em Python, o comando PLAY do MSX usado no livro
"Curso de Música" (Barbieri & Piazzi, Aleph, 1988).

A ideia é poder escrever uma melodia EXATAMENTE como no livro, por exemplo:

    PLAY "o4 L4 c d e f g a b"          (no MSX, em BASIC)
    tocar("o4 L4 c d e f g a b")        (aqui, em Python)

e ouvir o resultado, podendo discutir em aula CADA conceito musical
(altura, oitava, duração, andamento, sustenido, bemol...).

------------------------------------------------------------------------
COMO O COMPUTADOR "SABE" QUE ALTURA TOCAR?  (sistema temperado)
------------------------------------------------------------------------
O livro conta (Aula 6) que J. S. Bach popularizou o "sistema temperado":
a oitava é dividida em 12 semitons IGUAIS. É exatamente esse sistema que
o MSX usa - e que usamos aqui.

A regra matemática do sistema temperado é uma só:

    cada semitom que se sobe MULTIPLICA a frequência por 2^(1/12)

Subir 12 semitons (uma oitava inteira) multiplica por (2^(1/12))^12 = 2,
ou seja: uma oitava acima = o DOBRO da frequência. Esse é o conceito de
oitava do livro (a menor distância entre duas notas de mesmo nome).

Tomamos como referência o Lá central (A4 = 440 Hz), o "lá do diapasão".

Requisitos: nenhum pacote externo. Usa winsound (já vem no Windows) para
tocar ao vivo, e o módulo 'wave' (biblioteca padrão) para gravar .wav.
"""

import re
import math
import time
import struct
import wave

# ----------------------------------------------------------------------
# 1) NOMES DAS NOTAS  ->  POSIÇÃO EM SEMITONS DENTRO DA OITAVA
# ----------------------------------------------------------------------
# O MSX (e os países de língua inglesa) usa a notação por CIFRAS, em que
# cada letra é uma nota, como o livro ensina na Aula 2:
#
#       Dó  Ré  Mi  Fá  Sol  Lá  Si
#        C   D   E   F   G    A   B
#
# Contamos os semitons a partir do Dó (C = 0). Repare que entre Mi-Fá e
# entre Si-Dó NÃO existe tecla preta: a distância ali já é de meio tom.
SEMITOM_DA_NOTA = {
    "c": 0,   # Dó
    "d": 2,   # Ré   (1 tom acima de Dó -> pula o Dó#)
    "e": 4,   # Mi   (1 tom acima de Ré)
    "f": 5,   # Fá   (apenas MEIO tom acima de Mi!)
    "g": 7,   # Sol
    "a": 9,   # Lá   (A4 = 440 Hz é a nossa referência)
    "b": 11,  # Si   (meio tom abaixo do Dó da oitava seguinte)
}

# Nome em português, útil para imprimir na tela durante a aula.
NOME_PT = {
    "c": "Dó", "d": "Ré", "e": "Mi", "f": "Fá",
    "g": "Sol", "a": "Lá", "b": "Si",
}


def nota_para_frequencia(cifra, oitava=4, acidente=0):
    """Converte uma nota musical em frequência (Hz), no sistema temperado.

    cifra    : letra da nota, 'c'..'b' (Dó..Si)
    oitava   : número da oitava do MSX (1 a 8). O Dó central é o4 (oitava 4).
    acidente : +1 = sustenido (meio tom acima), -1 = bemol (meio tom abaixo).

    O cálculo passa por um "número de semitons" absoluto, no mesmo estilo
    do padrão MIDI, e depois aplica a fórmula do sistema temperado.
    """
    # Posição absoluta da nota, contada em semitons a partir do Dó da oitava 0.
    # (oitava * 12) avança uma oitava inteira (12 semitons) por vez.
    semitom_absoluto = (oitava + 1) * 12 + SEMITOM_DA_NOTA[cifra] + acidente

    # Referência do sistema temperado: Lá central A4 = 440 Hz.
    # Em semitons absolutos, esse Lá vale (4+1)*12 + 9 = 69 (o famoso "MIDI 69").
    LA_REFERENCIA = 69

    # Fórmula do sistema temperado:
    #   frequência = 440 * 2^((nota - 69) / 12)
    # Cada degrau de 1 no expoente é 1 semitom; 12 degraus dobram a frequência.
    return 440.0 * (2.0 ** ((semitom_absoluto - LA_REFERENCIA) / 12.0))


# ----------------------------------------------------------------------
# 2) O TRADUTOR DA "STRING DO PLAY"  ->  LISTA DE EVENTOS (nota, duração)
# ----------------------------------------------------------------------
# Sub-comandos reconhecidos (os mesmos do Apêndice C do livro):
#
#   o<n>   oitava (1 a 8)              -> Ox
#   L<n>   duração padrão das figuras  -> Lx   (1=semibreve ... 4=semínima ...)
#   T<n>   andamento (semínimas/min)   -> Tx   (32 = lento ... 255 = rapidíssimo)
#   V<n>   volume/intensidade (0..15)  -> Vx
#   r<n>   pausa (silêncio)            -> Rx
#   c..b   nota, com # + (sustenido) ou - (bemol), e duração opcional
#   N<n>   nota pelo número (0 a 96)   -> Nx   (cada +1 sobe um semitom)
#   s / m  envelope -> aqui são apenas IGNORADOS (timbre fica fora do escopo)

# Expressão regular que "fatia" a string do PLAY em sub-comandos (tokens).
_TOKEN = re.compile(r"""
    (?P<oitava>   o\d+ )                      |
    (?P<Ldur>     l\d+ )                      |
    (?P<tempo>    t\d+ )                       |
    (?P<volume>   v\d+ )                      |
    (?P<numero>   n\d+ )                       |
    (?P<pausa>    r\d* \.* )                    |
    (?P<nota>     [a-g] [#+\-]? \d* \.* )       |
    (?P<envelope> [sm]\d+ )
""", re.VERBOSE | re.IGNORECASE)


def traduzir(play_string, oitava=4, L=4, tempo=120, volume=15):
    """Traduz uma string estilo PLAY numa lista de eventos sonoros.

    Cada evento é um dicionário:
        {"freq": Hz ou None p/ pausa, "dur": segundos, "vol": 0..15,
         "rotulo": texto para mostrar em aula}

    Os parâmetros são o ESTADO INICIAL; eles vão mudando conforme os
    sub-comandos o/L/T/V aparecem na string, igualzinho ao MSX (onde, por
    exemplo, uma vez dado 'o3' todas as notas seguintes ficam na oitava 3).
    """
    eventos = []

    def segundos_da_figura(valor_L, pontos):
        """Converte uma figura musical em SEGUNDOS.

        valor_L : 1=semibreve, 2=mínima, 4=semínima, 8=colcheia, 16=semicolcheia...
                  (o número é o denominador: a figura dura 1/valor da semibreve)
        pontos  : nº de pontos de aumento ('.').

        Andamento (T): por convenção, T = quantas SEMÍNIMAS cabem em 1 minuto.
        Logo cada semínima dura 60/T segundos. Uma figura L vale (4/valor_L)
        semínimas, pois a semínima é L4.
        """
        seminimas = 4.0 / valor_L
        dur = seminimas * (60.0 / tempo)
        # Ponto de aumento (Aula 3): cada ponto soma METADE do valor anterior.
        #  1 ponto  -> x (1 + 1/2)         = x * 1,5
        #  2 pontos -> x (1 + 1/2 + 1/4)   = x * 1,75
        acrescimo, fator = 0.5, 0.0
        for _ in range(pontos):
            fator += acrescimo
            acrescimo /= 2
        return dur * (1 + fator)

    for m in _TOKEN.finditer(play_string):
        tipo = m.lastgroup
        txt = m.group().lower()

        if tipo == "oitava":
            oitava = int(txt[1:])

        elif tipo == "Ldur":
            L = int(txt[1:])                      # novo valor padrão de duração

        elif tipo == "tempo":
            tempo = int(txt[1:])                  # novo andamento

        elif tipo == "volume":
            volume = int(txt[1:])                 # nova intensidade

        elif tipo == "pausa":
            pontos = txt.count(".")
            corpo = txt.strip(".")[1:]            # dígitos depois do 'r'
            valor_L = int(corpo) if corpo else L
            eventos.append({
                "freq": None,
                "dur": segundos_da_figura(valor_L, pontos),
                "vol": volume,
                "rotulo": "(silêncio)",
            })

        elif tipo == "nota":
            cifra = txt[0]
            resto = txt[1:]
            acidente = 0
            if resto[:1] in ("#", "+"):           # sustenido
                acidente, resto = +1, resto[1:]
            elif resto[:1] == "-":                # bemol
                acidente, resto = -1, resto[1:]
            pontos = resto.count(".")
            corpo = resto.strip(".")
            valor_L = int(corpo) if corpo else L
            sinal = {1: "#", -1: "b", 0: ""}[acidente]
            eventos.append({
                "freq": nota_para_frequencia(cifra, oitava, acidente),
                "dur": segundos_da_figura(valor_L, pontos),
                "vol": volume,
                "rotulo": NOME_PT[cifra] + sinal + str(oitava),
            })

        elif tipo == "numero":
            # Nx: nota pelo número (0..96). Cada unidade = 1 semitom (Aula 2).
            n = int(txt[1:])
            if n == 0:
                eventos.append({"freq": None, "dur": segundos_da_figura(L, 0),
                                "vol": volume, "rotulo": "(silêncio)"})
            else:
                # Reaproveita a referência A4=440 (semitom absoluto 69).
                freq = 440.0 * (2.0 ** ((n + 24 - 69) / 12.0))
                eventos.append({"freq": freq, "dur": segundos_da_figura(L, 0),
                                "vol": volume, "rotulo": "N%d" % n})

        # 'envelope' (s/m) é ignorado de propósito: trata de timbre.

    return eventos


# ----------------------------------------------------------------------
# 3) TOCAR AO VIVO (winsound) E GRAVAR EM .WAV
# ----------------------------------------------------------------------
def tocar(play_string, oitava=4, L=4, tempo=120, volume=15, mostrar=True):
    """Toca a melodia AO VIVO, no estilo "bipe" do MSX (onda quadrada).

    Usa winsound.Beep, que só existe no Windows. Se quiser rodar em outro
    sistema, use gravar_wav() e abra o arquivo num tocador qualquer.
    """
    import winsound  # importado aqui para a biblioteca ainda carregar fora do Windows

    for ev in traduzir(play_string, oitava, L, tempo, volume):
        if mostrar:
            print("  %-10s  %5.0f ms" %
                  (ev["rotulo"], ev["dur"] * 1000))
        if ev["freq"] is None:
            time.sleep(ev["dur"])                 # pausa = silêncio
        else:
            # winsound.Beep exige frequência inteira entre 37 e 32767 Hz.
            f = max(37, min(32767, int(round(ev["freq"]))))
            winsound.Beep(f, max(1, int(ev["dur"] * 1000)))


def gravar_wav(play_string, arquivo, oitava=4, L=4, tempo=120, volume=15,
               taxa=44100):
    """Grava a melodia num arquivo .wav usando ONDA QUADRADA.

    A onda quadrada é o timbre típico do chip de som (PSG) do MSX: é um som
    "eletrônico", bem diferente do timbre suave de uma flauta. Gravar em wav
    é útil para usar a música em slides/vídeos da aula, ou em outro sistema.
    """
    quadros = bytearray()
    amplitude_max = 18000  # bem abaixo do teto de 32767 p/ não distorcer

    for ev in traduzir(play_string, oitava, L, tempo, volume):
        n_amostras = int(taxa * ev["dur"])
        if ev["freq"] is None:
            # Pausa: amostras em silêncio (valor zero).
            quadros += struct.pack("<%dh" % n_amostras, *([0] * n_amostras))
            continue

        # Volume 0..15 do MSX -> amplitude proporcional do som.
        amp = int(amplitude_max * (ev["vol"] / 15.0))
        # Quantas amostras dura UM ciclo completo da onda nessa frequência.
        amostras_por_ciclo = taxa / ev["freq"]
        bloco = []
        for i in range(n_amostras):
            # Onda quadrada: +amp na 1ª metade do ciclo, -amp na 2ª metade.
            fase = (i % amostras_por_ciclo) / amostras_por_ciclo
            bloco.append(amp if fase < 0.5 else -amp)
        quadros += struct.pack("<%dh" % n_amostras, *bloco)

    with wave.open(arquivo, "w") as w:
        w.setnchannels(1)        # mono (o MSX deste exemplo toca 1 voz)
        w.setsampwidth(2)        # 16 bits por amostra
        w.setframerate(taxa)
        w.writeframes(bytes(quadros))
    print("Arquivo gravado: %s" % arquivo)


# ----------------------------------------------------------------------
# Demonstração rápida quando rodamos:  python msx_music.py
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Tocando a escala de Dó maior (o4 L4 c d e f g a b o5 c)...")
    tocar("o4 L4 c d e f g a b o5 c")
