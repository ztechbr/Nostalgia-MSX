# Exemplos de Música em Python — baseados no *Curso de Música* (MSX)

Estes exemplos recriam, em Python, o **comando PLAY do MSX** usado no livro
*Curso de Música, vol. 1* (Barbieri & Piazzi, Editora Aleph, 1988), para usar
em aulas de música. Cada conceito musical do livro vira código **comentado**
que o aluno pode ouvir, alterar e experimentar.

## Como rodar

Precisa apenas de **Python 3** no **Windows** (usa o `winsound`, que já vem
instalado, para tocar os "bipes" no estilo do chip de som do MSX).

```
python 01_altura.py
```

> Os exemplos tocam som ao vivo. Em sala, ligue o computador a uma caixa de som.
> Vários exemplos também geram um arquivo **`.wav`** (ex.: `parabens.wav`) que
> você pode usar em slides, vídeos ou em qualquer outro computador.

## Os arquivos

| Arquivo | Conceito musical | Aula do livro |
|---|---|---|
| `msx_music.py` | **Biblioteca base.** Traduz a notação do PLAY em som e explica o sistema temperado (a fórmula que liga nota → frequência). | Apêndice C |
| `01_altura.py` | Altura (grave/médio/agudo), oitavas, cifras (C D E F G A B). | Aula 2 |
| `02_duracao.py` | Figuras (semibreve, mínima, semínima...), ponto de aumento, pausas, andamento e dinâmica. | Aula 3 |
| `03_escalas.py` | Escala diatônica, estrutura T-T-S-T-T-T-S, modos gregos. | Aula 5 |
| `04_acidentes.py` | Sustenido/bemol, tom × semitom, enarmonia, sistema temperado. | Aula 6 |
| `05_transposicao.py` | Transpor melodia ("pastorzinho") e a "armadilha" do bemol. | Aula 5 |
| `06_musica_completa.py` | Peça inteira transcrita: *Parabéns pra Você*. | Exercício 6.8 |

## A notação (igual à do livro)

As notas seguem a **cifra anglo-saxônica** do MSX:

```
Dó  Ré  Mi  Fá  Sol  Lá  Si
 C   D   E   F   G    A   B
```

Sub-comandos reconhecidos (os mesmos do Apêndice C):

| Comando | Significado | Exemplo |
|---|---|---|
| `o<n>` | oitava (1–8); o Dó central é `o4` | `o4` |
| `L<n>` | duração padrão (1=semibreve, 4=semínima, 8=colcheia...) | `L8` |
| `T<n>` | andamento (semínimas por minuto) | `T120` |
| `V<n>` | volume/intensidade (0–15) | `V15` |
| `#` `+` | sustenido (sobe meio tom) | `c#` |
| `-` | bemol (desce meio tom) | `b-` |
| `.` | ponto de aumento | `a2.` |
| `r<n>` | pausa (silêncio) | `r4` |

Exemplo mínimo:

```python
import msx_music as msx
msx.tocar("o4 L4 c d e f g a b o5 c")   # toca a escala de Dó maior
```

## Sugestão de uso em aula

1. Toque o exemplo como está.
2. Mostre o trecho comentado correspondente ao conceito.
3. Peça aos alunos para **alterar um parâmetro** (a oitava, o `T`, um `#`) e
   ouvir o efeito — a descoberta pelo ouvido é exatamente a proposta do livro.
