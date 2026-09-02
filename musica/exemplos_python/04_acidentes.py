# -*- coding: utf-8 -*-
"""
EXEMPLO 4 - ACIDENTES, TOM/SEMITOM E TEMPERAMENTO   [Livro: Aula 6]
===================================================================

ACIDENTES são sinais que ALTERAM a altura de uma nota em meio tom:

   SUSTENIDO (#)  ->  SOBE meio tom    (no MSX: # ou +)
   BEMOL     (b)  ->  DESCE meio tom   (no MSX: -)

Eles surgem quando, ao construir uma escala maior a partir de outra nota,
precisamos "consertar" a estrutura T-T-S-T-T-T-S (Aula 6).

Conceitos demonstrados:
  - sustenido e bemol na prática
  - TOM x SEMITOM (1 tom = 2 semitons)
  - ENARMONIA: duas notas com nomes diferentes e a MESMA altura (Lá# = Sib)
  - o SISTEMA TEMPERADO de Bach: 12 semitons IGUAIS na oitava

Rode com:   python 04_acidentes.py
"""

import msx_music as msx

# ----------------------------------------------------------------------
# (a) SUSTENIDO E BEMOL: subir e descer meio tom
# ----------------------------------------------------------------------
# Tocamos Dó, depois Dó# (meio tom acima), depois Dó de novo.
# E Ré, depois Réb (meio tom abaixo), depois Ré.
print("(a) Sustenido sobe meio tom; bemol desce meio tom:")
print("    Dó  ->  Dó#  ->  Dó")
msx.tocar("o4 c2 c#2 c2", mostrar=True)
print("    Ré  ->  Réb  ->  Ré")
msx.tocar("o4 d2 d-2 d2", mostrar=True)


# ----------------------------------------------------------------------
# (b) TOM x SEMITOM
# ----------------------------------------------------------------------
# 1 TOM = 2 semitons. Vamos ouvir e medir as duas distâncias:
#   - Dó -> Dó#  é um SEMITOM (passo pequeno)
#   - Dó -> Ré   é um TOM     (passo "dobrado", pois pula o Dó#)
print("\n(b) Comparando um SEMITOM e um TOM a partir do Dó:")
for nome, par in [("SEMITOM (Dó->Dó#)", "c2 c#2"),
                  ("TOM     (Dó->Ré )", "c2 d2")]:
    ev = [e for e in msx.traduzir("o4 " + par) if e["freq"]]
    razao = ev[1]["freq"] / ev[0]["freq"]
    semitons = round(12 * __import__("math").log2(razao))
    print("  %s  -> %d semitom(ns)" % (nome, semitons))
    msx.tocar("o4 " + par, L=2, mostrar=False)


# ----------------------------------------------------------------------
# (c) ENARMONIA: Lá# e Sib são a MESMA altura
# ----------------------------------------------------------------------
# O livro mostra que Lá# (meio tom ACIMA do Lá) e Sib (meio tom ABAIXO do Si)
# caem exatamente no mesmo lugar - a tecla preta entre Lá e Si. Os nomes são
# diferentes só porque vêm de escalas diferentes.
print("\n(c) Enarmonia: Lá# e Sib têm a MESMA frequência:")
f_la_sust = msx.nota_para_frequencia("a", oitava=4, acidente=+1)   # Lá#
f_si_bem  = msx.nota_para_frequencia("b", oitava=4, acidente=-1)   # Sib
print("  Lá# = %.2f Hz" % f_la_sust)
print("  Sib = %.2f Hz" % f_si_bem)
print("  Iguais?", "SIM" if round(f_la_sust, 2) == round(f_si_bem, 2) else "não")
msx.tocar("o4 a#2 b-2", mostrar=True)   # devem soar idênticas


# ----------------------------------------------------------------------
# (d) O SISTEMA TEMPERADO: as 12 notas da oitava, todas igualmente espaçadas
# ----------------------------------------------------------------------
# Bach popularizou dividir a oitava em 12 semitons IGUAIS. Tocando a escala
# CROMÁTICA (todos os 12 semitons), ouvimos passos sempre do mesmo tamanho.
# É por isso que existem as teclas pretas do piano!
print("\n(d) Escala CROMÁTICA - os 12 semitons iguais do sistema temperado:")
cromatica = "o4 c c# d d# e f f# g g# a a# b o5 c"
msx.tocar(cromatica, L=8, tempo=160, mostrar=True)

# Mostra que a razão entre semitons vizinhos é sempre a mesma constante:
# 2^(1/12) ≈ 1.0595. É a "impressão digital" do sistema temperado.
import math
print("\n  Razão de frequência entre semitons vizinhos (deve ser ~1.0595):")
ev = [e for e in msx.traduzir(cromatica) if e["freq"]]
for a, b in list(zip(ev, ev[1:]))[:4]:
    print("    %6.2f Hz -> %6.2f Hz   razão = %.4f"
          % (a["freq"], b["freq"], b["freq"] / a["freq"]))
print("    (2 elevado a 1/12 = %.4f)" % (2 ** (1 / 12)))
