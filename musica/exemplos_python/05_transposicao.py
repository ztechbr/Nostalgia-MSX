# -*- coding: utf-8 -*-
"""
EXEMPLO 5 - TRANSPOSIÇÃO DE UMA MELODIA            [Livro: Aula 5]
==================================================================

TRANSPOR é tocar a MESMA melodia mais grave ou mais aguda, deslocando
todas as notas pela mesma quantidade de degraus. A melodia continua
"a mesma" (reconhecível), só muda a região de altura.

O livro faz isso com a cantiga do "pastorzinho":

      Dó Ré Mi Fá .. Fá Fá ..
      Dó Ré Dó Ré .. Ré Ré ..
      Dó Sol Fá Mi .. Mi Mi ..
      Dó Ré Mi Fá .. Fá Fá ..

E mostra uma ARMADILHA importante: ao transpor, às vezes um intervalo que
deveria ser de meio tom vira um tom inteiro. Aí precisamos de um ACIDENTE
(no caso, um bemol) para a melodia continuar "certinha".

Rode com:   python 05_transposicao.py
"""

import msx_music as msx

# Cantiga do "pastorzinho", exatamente como no livro (Figura 5.18).
# 'r' são as pausas; L4 = semínimas; o4 = oitava central.
PASTORZINHO = (
    "s0 m5000 L4 T180 o4 "
    "c d e f r f f r "      # Dó Ré Mi Fá .. Fá Fá
    "c d c d r d d r "      # Dó Ré Dó Ré .. Ré Ré
    "c g f e r e e r "      # Dó Sol Fá Mi .. Mi Mi
    "c d e f r f f r "      # Dó Ré Mi Fá .. Fá Fá
)

print("(a) Cantiga original (na oitava 4):")
msx.tocar(PASTORZINHO, mostrar=False)


# ----------------------------------------------------------------------
# (b) TRANSPONDO "NA MÃO", como o livro faz
# ----------------------------------------------------------------------
# O livro transpõe a cantiga para começar 3 notas ACIMA (em Fá). Ao fazer
# isso, o trecho "Lá Si" aparece onde precisávamos de apenas meio tom -
# então BEMOLIZAMOS o Si (b-) para corrigir. Note os "b-" abaixo.
print("\n(b) Transposta para começar em Fá (com Sib para 'consertar'):")
TRANSPOSTA = (
    "s0 m5000 L4 T180 o4 "
    "f g a b- r b- b- r "        # repare no Si BEMOL (b-)
    "f g f g r g g r "
    "f o5 c o4 b- a r a a r "
    "f g a b- r b- b- r "
)
msx.tocar(TRANSPOSTA, mostrar=False)
print("    (sem o bemol, o trecho 'desafinaria', como o livro alerta!)")


# ----------------------------------------------------------------------
# (c) TRANSPONDO COM O COMPUTADOR: deslocar N semitons automaticamente
# ----------------------------------------------------------------------
# Aqui está a vantagem do computador: em vez de reescrever a partitura,
# pedimos ao Python para subir/descer todas as notas o mesmo nº de semitons.
# Usamos o sub-comando Nx (nota por número), em que +1 = um semitom acima.
import math


def transpor(play_string, semitons):
    """Devolve a lista de eventos da melodia deslocada em 'semitons'.

    Convertendo cada frequência num número de semitons absoluto, somamos o
    deslocamento e voltamos para frequência. Assim a melodia inteira sobe
    (semitons>0) ou desce (semitons<0) mantendo a forma.
    """
    novos = []
    for ev in msx.traduzir(play_string):
        if ev["freq"] is None:
            novos.append(ev)
            continue
        n = 12 * math.log2(ev["freq"] / 440.0) + 69      # semitom absoluto
        nova_freq = 440.0 * 2 ** ((round(n) + semitons - 69) / 12.0)
        e = dict(ev)
        e["freq"] = nova_freq
        novos.append(e)
    return novos


def tocar_eventos(eventos):
    """Toca uma lista de eventos já pronta (reaproveita o motor de áudio)."""
    import winsound
    import time
    for ev in eventos:
        if ev["freq"] is None:
            time.sleep(ev["dur"])
        else:
            f = max(37, min(32767, int(round(ev["freq"]))))
            winsound.Beep(f, max(1, int(ev["dur"] * 1000)))


print("\n(c) A MESMA cantiga deslocada automaticamente pelo computador:")
for desloc in (-5, 0, +5, +12):
    sentido = ("%+d semitons" % desloc) if desloc else "original"
    if desloc == 12:
        sentido += " (uma oitava acima)"
    print("   ", sentido)
    tocar_eventos(transpor(PASTORZINHO, desloc))
