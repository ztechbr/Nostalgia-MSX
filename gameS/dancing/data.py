"""
Game data extracted / adapted from the original TRS-80 Color Computer
program "Dancing Demon" (PowerSoft Products, (c) 1979, 1986 Leo Christopherson).

Note table (from the original ENTER MUSICAL SCORE help screen):
    C1=A  F1=F   A1#=K  D2#=P  G2#=U
    C1#=B F1#=G  B1 =L  E2 =Q  A2 =V
    D1=C  G1=H   C2=M   F2=R   A2#=W
    D1#=D G1#=I  C2#=N  F2#=S  B2=X
    E1=E  A1=J   D2=O   G2=T   C3=Y
    Z = rest

That is a straight chromatic scale: A..Y = 25 semitones (two octaves + 1),
Z = rest.

Dance routine table (from the ENTER DANCE ROUTINES help screen):
    A---STEP--#1-----2   I---STEP--#7-----4   R,S-MOVE--#1-L,R-1
    B---STEP--#2-----2   J---SQUAT--------1   T,U-MOVE--#2-L,R-2
    C---STEP--#3-----2   K---STAND--------1   V,W-MOVE--#3-L,R-2
    D,E-STEP--#4-L,R-2   L,M-STOMP-#1-L,R-1   X---FAST JUMP----1
    F,G-STEP--#5-L,R-2   N,O-STOMP-#2-L,R-4   Y---SPIN JUMP----2
    H---STEP--#6-----3   P,Q-TURN-----L,R-2   Z---SLOW JUMP----2
"""

# ---------------------------------------------------------------- notes ----
NOTE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXY"  # A..Y = 25 chromatic semitones
NOTE_NAMES = [
    "C1", "C1#", "D1", "D1#", "E1", "F1", "F1#", "G1", "G1#", "A1", "A1#",
    "B1", "C2", "C2#", "D2", "D2#", "E2", "F2", "F2#", "G2", "G2#", "A2",
    "A2#", "B2", "C3",
]
REST_LETTER = "Z"

# Base frequency used for the program's "C1". The real TRS-80 tone
# generator ran quite low; we pick a modern-speaker-friendly middle C
# so the tunes are pleasant on laptop speakers.
BASE_FREQ = 261.63  # Hz, real-world C4


def note_frequency(letter: str):
    """Return the frequency in Hz for a note letter, or None if it's a rest."""
    letter = letter.upper()
    if letter == REST_LETTER:
        return None
    if letter not in NOTE_LETTERS:
        return None
    semitone = NOTE_LETTERS.index(letter)
    return BASE_FREQ * (2 ** (semitone / 12))


# --------------------------------------------------------------- routine ---
# letter -> (label, beats, move-kind, direction)  direction: 0 none, -1 left, 1 right
ROUTINE_TABLE = {
    "A": ("STEP #1", 2, "step", 0),
    "B": ("STEP #2", 2, "step", 0),
    "C": ("STEP #3", 2, "step", 0),
    "D": ("STEP #4 (L)", 2, "step", -1),
    "E": ("STEP #4 (R)", 2, "step", 1),
    "F": ("STEP #5 (L)", 2, "step", -1),
    "G": ("STEP #5 (R)", 2, "step", 1),
    "H": ("STEP #6", 3, "step", 0),
    "I": ("STEP #7", 4, "step", 0),
    "J": ("SQUAT", 1, "squat", 0),
    "K": ("STAND", 1, "stand", 0),
    "L": ("STOMP #1 (L)", 1, "stomp", -1),
    "M": ("STOMP #1 (R)", 1, "stomp", 1),
    "N": ("STOMP #2 (L)", 4, "stomp", -1),
    "O": ("STOMP #2 (R)", 4, "stomp", 1),
    "P": ("TURN (L)", 2, "turn", -1),
    "Q": ("TURN (R)", 2, "turn", 1),
    "R": ("MOVE #1 (L)", 1, "move", -1),
    "S": ("MOVE #1 (R)", 1, "move", 1),
    "T": ("MOVE #2 (L)", 2, "move", -1),
    "U": ("MOVE #2 (R)", 2, "move", 1),
    "V": ("MOVE #3 (L)", 2, "move", -1),
    "W": ("MOVE #3 (R)", 2, "move", 1),
    "X": ("FAST JUMP", 1, "jump", 0),
    "Y": ("SPIN JUMP", 2, "spinjump", 0),
    "Z": ("SLOW JUMP", 2, "slowjump", 0),
}

MAX_NOTES = 248
MAX_ROUTINE = 248

# ----------------------------------------------------------- preset shows --
# These sequences were recovered as embedded plain-text strings inside the
# tokenized .bas files (dncdm86a.bas / dncdm86b.bas). The engine mechanics
# above are transcribed directly from the on-screen instructions; these
# preset shows are the authentic note/routine letter strings bundled with
# the two original program disks.
PRESET_SHOWS = [
    {
        "name": "Disk A - Finale",
        "dance": "LLLDEDECCCCBKKBKKDEDENOLMLMDENOLMLMDEFGFGCCCCBKKBKKDEDERSSRRSSRSRRSSRRSDECCMLMLM",
        "music": "MOQRZMJHFZHJZMZRQZRTZHJLZOZTZZZZZZZQZOMQOZMOOOOZZZZTZQOTQZOMMMMZMOQRZMJHFZHJZMZRQZRTZHJLZOZTZZZZZZZTZRQTRZOQZQZQOZMOZQRTZMZRZZZZ",
    },
    {
        "name": "Disk B - Finale",
        "dance": "BXHHLMHHLMHHSSHHSSFJGJLMFJGJLMPKPJLHH",
        "music": "CCCHZZLZCCCHZZLZZZZZHZHGGEECZZZZCCCGZZJZCCCGZZJZZZZZOZQOMLJHZZZZ",
    },
    {
        "name": "Classic Jig",
        "dance": "AAZZCEDZZJJTTPPUQUQSSSSFGQQFGRRRREDPPEZZ",
        "music": "ECACEEEZCCCZEHHZECACEEEECCECAZZZ",
    },
    {
        "name": "Routine Six",
        "dance": "JJJFGFGFGFGDEDEFGFGLMFMLGLMFMLGDEDEFGFGAAAAAAAZAAAAEDEDTTQQQQRRRRDEDEFGJ",
        "music": "EFHJZIZHZZZJJIIHZZJMMLLJJHFEZCZAEFHJZIZHZZHJJIIHZZJMMLLJJHFEZCZAMMJMZZZZMMMMZHZZMMJMZZZZMMMMHHGFFECJZIZHZZHJJIIHZZJMMLLJJHFEZCZA",
    },
    {
        "name": "Routine Eight",
        "dance": "JJFJGJFJGJDSESFJGJQLQLFJGJRRRRRRJJKYJRVRVRVRVBXHHYXQMQMQMQMIKJIKJFJGJFJGJDJEJFJK",
        "music": "EFHZAZQOMZEZLJHZZCHFEZZZEFHZAZQOMZEZLJHZZCFEAZZZCEFZOMLJHZMZLMOZZCLJHZGFEFHZAZMMLJZZCEHZZHJLMZZZ",
    },
]

# Little flourish used on the original title screen while the credits print
INTRO_JIG = "AAXXAAXX"
