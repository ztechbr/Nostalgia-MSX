# -*- coding: utf-8 -*-
"""
EXEMPLO 3 - ESCALAS E MODOS GREGOS              [Livro: Aula 5]
===============================================================

ESCALA é uma sucessão ordenada de notas. A escala mais antiga do Ocidente é
a DIATÔNICA (de Pitágoras / Ptolomeu): 7 notas que, somadas, dão uma oitava.

O segredo de uma escala NÃO está nas notas em si, mas na ESTRUTURA de
intervalos entre elas - onde ficam os TONS (T) e os SEMITONS (S).

Lembre (Aula 6):  1 TOM = 2 semitons.  No teclado, um semitom é a menor
distância possível (tecla vizinha, incluindo as pretas).

Modos GREGOS (precursores das escalas atuais): são a MESMA sequência de
teclas brancas, mas COMEÇANDO em notas diferentes. Como o ponto de partida
muda, a ordem de tons e semitons muda - e o "clima" da escala muda também.

   modo jônico   começa em Dó (C)  -> é a nossa ESCALA MAIOR
   modo dórico   começa em Ré (D)
   modo frígio   começa em Mi (E)
   modo lídio    começa em Fá (F)
   modo mixolídio começa em Sol (G)

Rode com:   python 03_escalas.py
"""

import msx_music as msx


def estrutura_de_intervalos(play_string):
    """Calcula e mostra os intervalos (Tom / Semitom) entre notas vizinhas.

    Esta é a parte MAIS pedagógica: traduzimos a melodia em frequências e,
    de uma nota para a próxima, medimos quantos semitons há. 12 semitons
    cabem numa oitava, e 1 tom = 2 semitons.
    """
    eventos = [e for e in msx.traduzir(play_string) if e["freq"] is not None]
    partes = []
    for anterior, atual in zip(eventos, eventos[1:]):
        # nº de semitons = quantos passos de 2^(1/12) separam as frequências
        semitons = round(12 * (__import__("math").log2(atual["freq"] / anterior["freq"])))
        if semitons == 2:
            partes.append("T")        # tom
        elif semitons == 1:
            partes.append("S")        # semitom
        else:
            partes.append(str(semitons))
    return " ".join(partes)


# ----------------------------------------------------------------------
# (a) A ESCALA MAIOR (modo jônico) E SUA ESTRUTURA T-T-S-T-T-T-S
# ----------------------------------------------------------------------
# Toda escala MAIOR tem SEMPRE esta estrutura de intervalos:
#       T  T  S  T  T  T  S
# Os dois semitons ficam entre Mi-Fá (3º-4º grau) e Si-Dó (7º-8º grau).
print("(a) Escala de DÓ MAIOR (modo jônico)")
do_maior = "o4 c d e f g a b o5 c"
print("    Estrutura de intervalos:", estrutura_de_intervalos(do_maior),
      "  <- toda escala maior é assim!")
msx.tocar(do_maior, L=4, tempo=140, mostrar=True)


# ----------------------------------------------------------------------
# (b) OS MODOS GREGOS: mesmas teclas brancas, começos diferentes
# ----------------------------------------------------------------------
# Tocamos só teclas brancas (sem sustenidos/bemóis), mudando a nota inicial.
# Ouça como cada modo tem um "caráter" próprio, mesmo usando as mesmas notas.
print("\n(b) Modos gregos (só teclas brancas, começando em notas diferentes):")
modos = {
    "Jônico  (Dó->Dó) = MAIOR": "o4 c d e f g a b o5 c",
    "Dórico  (Ré->Ré)":         "o4 d e f g a b o5 c d",
    "Frígio  (Mi->Mi)":         "o4 e f g a b o5 c d e",
    "Lídio   (Fá->Fá)":         "o4 f g a b o5 c d e f",
    "Mixolídio (Sol->Sol)":     "o4 g a b o5 c d e f g",
}
for nome, melodia in modos.items():
    print("  %-26s  intervalos: %s" % (nome, estrutura_de_intervalos(melodia)))
    msx.tocar(melodia, L=8, tempo=160, mostrar=False)


# ----------------------------------------------------------------------
# (c) POR QUE O MODO DÓRICO "SOA DIFERENTE" DO MAIOR
# ----------------------------------------------------------------------
# O livro (Aula 6) compara o modo dórico (em Ré, teclas brancas) com a
# escala MAIOR de Ré. A diferença é que o dórico tem Fá e Dó NATURAIS,
# enquanto Ré maior precisa de Fá# e Dó# para virar T-T-S-T-T-T-S.
print("\n(c) Comparando o modo dórico de Ré com a escala de RÉ MAIOR:")
re_dorico = "o4 d e f g a b o5 c d"          # teclas brancas
re_maior  = "o4 d e f#  g a b o5 c# d"       # com 2 sustenidos -> vira MAIOR
print("  Dórico de Ré :", estrutura_de_intervalos(re_dorico))
msx.tocar(re_dorico, L=8, tempo=150, mostrar=False)
print("  Ré MAIOR     :", estrutura_de_intervalos(re_maior), " <- T-T-S-T-T-T-S")
msx.tocar(re_maior, L=8, tempo=150, mostrar=False)
print("  (a 2ª versão usa Fá# e Dó# para 'consertar' a estrutura da escala maior)")
