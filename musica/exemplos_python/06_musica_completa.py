# -*- coding: utf-8 -*-
"""
EXEMPLO 6 - UMA MÚSICA COMPLETA, TRANSCRITA DO LIVRO   [Livro: E 6.8]
=====================================================================

Aqui juntamos TUDO: altura (notas e oitavas), duração (figuras e pontos),
andamento e acidentes, transcrevendo uma partitura inteira - exatamente
como o objetivo final do volume 1 do livro.

Esta é a "música universal" do exercício 6.8: o PARABÉNS PRA VOCÊ.
A transcrição é a do próprio livro (Figura 6.29), com:
  - g8.g16  -> colcheia PONTUADA + semicolcheia (o "balanço" do Parabéns!)
  - mudanças de oitava com o4 / o5
  - notas de durações variadas (semínima, mínima, etc.)

Rode com:   python 06_musica_completa.py
"""

import msx_music as msx

# Partitura completa, montada linha a linha como no livro.
# Cada par de linhas corresponde a um "Pa-ra-béns pra vo-cê".
PARABENS = (
    "s0 m6000 o4 T120 "
    "g8. g16 "              # "Pa-ra-"
    "a4 g4 o5 c4 "          # "béns  pra  vo-"
    "o4 b2 g8. g16 "        # "cê,    Pa-ra-"
    "a4 g4 o5 d4 "          # "béns  pra  vo-"
    "c2 e8. e16 "           # "cê.    Pa-ra-"
    "g4 e4 c4 "             # "béns  pra  vo-"
    "o4 b4 a4 o5 f8. f16 "  # "cê,    que-ri-do(a)-"
    "e4 c4 d4 "             # "  ...
    "c2 "                   # "cê"
)

print("Tocando o PARABÉNS PRA VOCÊ (transcrição do livro, Aula 6)...\n")
# mostrar=True imprime cada nota com seu nome em português e a duração em ms,
# ótimo para acompanhar a partitura junto com a turma.
msx.tocar(PARABENS, mostrar=True)

# Gera também um arquivo de áudio para você usar onde quiser.
msx.gravar_wav(PARABENS, "parabens.wav")

print("""
------------------------------------------------------------------
DESAFIO PARA A AULA:
  1) Troque o T120 por T180 e ouça o Parabéns mais 'apressado'.
  2) Troque 'o4' inicial por 'o3': a música inteira fica mais grave
     (você TRANSPÔS uma oitava abaixo!).
  3) Tente transcrever a 2ª parte ("é um bom amigo...") sozinho,
     escrevendo as notas no mesmo formato das linhas acima.
------------------------------------------------------------------
""")
