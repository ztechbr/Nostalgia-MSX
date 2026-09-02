# -*- coding: utf-8 -*-
"""
EXEMPLO 2 - DURAÇÃO, FIGURAS, PONTO E PAUSAS    [Livro: Aula 3]
===============================================================

A DURAÇÃO é quanto tempo um som se prolonga. Na partitura, a duração é
indicada pela FORMA da nota - são as "figuras":

   FIGURA          símbolo no MSX     dura...
   semibreve            L1            o dobro da mínima
   mínima               L2            o dobro da semínima
   semínima             L4            o dobro da colcheia   (= 1 "tempo")
   colcheia             L8            o dobro da semicolcheia
   semicolcheia         L16
   fusa                 L32
   semifusa             L64

Há uma RELAÇÃO MATEMÁTICA: cada figura dura o DOBRO da seguinte. Por isso,
no MSX, o número em Lx é o denominador da fração de semibreve (L4 = 1/4 de
semibreve = semínima).

Conceitos demonstrados:
  - figuras e suas durações relativas (potências de 2)
  - o PONTO DE AUMENTO (aumenta a nota em metade do seu valor)
  - as PAUSAS (silêncios), com Rx
  - o ANDAMENTO (Tx) e a INTENSIDADE/dinâmica (Vx)

Rode com:   python 02_duracao.py
"""

import msx_music as msx

# ----------------------------------------------------------------------
# (a) A MESMA MELODIA EM FIGURAS CADA VEZ MAIS CURTAS
# ----------------------------------------------------------------------
# É a Figura 3.5 do livro. A sequência de notas é idêntica; só muda o Lx.
# Como cada figura dura METADE da anterior, cada linha toca o DOBRO de
# rápido que a de cima.
print("(a) A mesma escala em durações diferentes (L1, L4, L16, L64):")
escala = "c d e f g a b o5 c o4 b a g f e d c"
for valor in (1, 4, 16, 64):
    nome = {1: "semibreve", 4: "semínima", 16: "semicolcheia", 64: "semifusa"}[valor]
    print("  L%-2d (%s):" % (valor, nome))
    msx.tocar(escala, oitava=4, L=valor, mostrar=False)


# ----------------------------------------------------------------------
# (b) O PONTO DE AUMENTO
# ----------------------------------------------------------------------
# O ponto aumenta a nota em METADE do seu valor:
#   "a2"  -> mínima
#   "a2." -> mínima + metade  = 1,5 mínima
#   "a2.."-> mínima + metade + um quarto = 1,75 mínima
# Repare como cada som dura um pouquinho mais que o anterior.
print("\n(b) Ponto de aumento (cada nota dura mais que a anterior):")
msx.tocar("a2  r4  a2.  r4  a2..", oitava=4, tempo=120, mostrar=True)


# ----------------------------------------------------------------------
# (c) PAUSAS: o silêncio também tem duração
# ----------------------------------------------------------------------
# A pausa (Rx) é tão importante quanto a nota - é o silêncio que dá ritmo.
# Aqui alternamos nota curta e pausa curta, criando um efeito "picotado".
print("\n(c) Notas e pausas alternadas (ritmo 'picotado'):")
msx.tocar("o4 c8 r8 c8 r8 c8 r8 c4 r4", mostrar=True)


# ----------------------------------------------------------------------
# (d) ANDAMENTO (Tx): a mesma música devagar e depressa
# ----------------------------------------------------------------------
# O andamento (T) é a velocidade da música - quantas semínimas por minuto.
# T pequeno = lento (adagio); T grande = rápido (presto). No MSX vai de 32 a 255.
print("\n(d) A mesma frase, devagar (T60) e depressa (T200):")
frase = "o4 L8 g f e d e f g4 g4"
print("  Lento  (T=60):")
msx.tocar(frase, tempo=60, mostrar=False)
print("  Rápido (T=200):")
msx.tocar(frase, tempo=200, mostrar=False)


# ----------------------------------------------------------------------
# (e) INTENSIDADE / DINÂMICA (Vx): forte e fraco
# ----------------------------------------------------------------------
# A intensidade é o quão FORTE ou FRACO soa. Na partitura usam-se termos
# italianos: p (piano=fraco), f (forte). No MSX, o volume V vai de 0 a 15.
# (A diferença de volume aparece principalmente no arquivo .wav gravado.)
print("\n(e) Mesma nota, intensidades diferentes - p (fraco) e f (forte):")
msx.tocar("v8 a2 r4 v15 a2", mostrar=True)

# Grava um .wav onde a diferença forte/fraco fica nítida:
msx.gravar_wav("o4 v8 c4 c4 c4 c4 v15 c4 c4 c4 c4",
               "dinamica_fraco_forte.wav", tempo=120)
