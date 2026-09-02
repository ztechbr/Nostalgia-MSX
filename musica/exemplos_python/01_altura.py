# -*- coding: utf-8 -*-
"""
EXEMPLO 1 - ALTURA (grave, médio, agudo)        [Livro: Aula 2]
===============================================================

A ALTURA é a primeira propriedade do som estudada no livro. É o que nos
faz dizer que um som é "grave" (baixo) ou "agudo" (alto). Fisicamente, a
altura corresponde à FREQUÊNCIA: quanto MAIOR a frequência, MAIS AGUDO o som.

Conceitos demonstrados aqui:
  - sons graves, médios e agudos                  (a "gama" do MSX)
  - a OITAVA: subir uma oitava DOBRA a frequência
  - a CIFRA (C D E F G A B = Dó Ré Mi Fá Sol Lá Si)

Para ouvir, basta rodar:   python 01_altura.py
"""

import msx_music as msx

# ----------------------------------------------------------------------
# (a) DO MAIS GRAVE AO MAIS AGUDO
# ----------------------------------------------------------------------
# Reproduz a ideia da Figura 2.1 do livro: percorrer a extensão do MSX,
# do som mais grave (oitava 1) ao mais agudo (oitava 8).
# Note como, ao subir, o som vai ficando cada vez mais "fininho".
print("(a) Toda a gama do MSX: do mais grave ao mais agudo")
for oitava in range(1, 9):
    print("  -- oitava %d --" % oitava)
    msx.tocar("c d e f g a b", oitava=oitava, L=16, tempo=200, mostrar=False)


# ----------------------------------------------------------------------
# (b) A OITAVA: o mesmo "Lá" em frequências que vão dobrando
# ----------------------------------------------------------------------
# A oitava é a menor distância entre duas notas de MESMO NOME (Lá-Lá).
# Mostramos a frequência calculada: cada oitava acima é o DOBRO da anterior.
# É a regra de ouro do sistema temperado (Aula 6).
print("\n(b) O Lá em várias oitavas - repare que a frequência DOBRA:")
for oitava in range(2, 7):
    freq = msx.nota_para_frequencia("a", oitava=oitava)
    print("  Lá da oitava %d  =  %7.2f Hz" % (oitava, freq))
    msx.tocar("a", oitava=oitava, L=2, mostrar=False)
# O Lá central (oitava 4) deve dar 440 Hz, o "lá do diapasão".


# ----------------------------------------------------------------------
# (c) A CIFRA: tocando as 7 notas com o nome aparecendo na tela
# ----------------------------------------------------------------------
# Útil para a turma associar a LETRA (cifra do MSX) ao NOME em português.
print("\n(c) As sete notas da oitava central (mostrando a cifra):")
print("    C=Dó  D=Ré  E=Mi  F=Fá  G=Sol  A=Lá  B=Si")
msx.tocar("o4 L2 c d e f g a b", mostrar=True)


# ----------------------------------------------------------------------
# (d) Para a aula: gravar um arquivo de áudio da escala
# ----------------------------------------------------------------------
# Gera um .wav que você pode colocar em slides ou tocar em qualquer máquina.
msx.gravar_wav("o4 L4 c d e f g a b o5 c", "escala_do_maior.wav", tempo=140)
