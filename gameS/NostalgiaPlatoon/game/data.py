"""Dados estáticos do jogo: salas, itens e inimigos.

Inspirado no clima de selva/guerra do cartucho de MSX "Platoon",
mas com mapa, itens e história próprios (não é uma cópia do ROM).
"""

ITEMS = {
    "m16": {
        "nome": "Fuzil M16",
        "aliases": ["m16", "fuzil", "rifle"],
        "descricao": "Um fuzil M16 emperrado na lama, mas ainda funcional.",
        "arma": True,
        "dano": (12, 22),
        "requer_municao": True,
    },
    "municao": {
        "nome": "Pente de Munição",
        "aliases": ["municao", "munição", "balas", "pente"],
        "descricao": "Um pente de munição extra para o M16.",
        "arma": False,
    },
    "facao": {
        "nome": "Facão",
        "aliases": ["facao", "facão", "machete"],
        "descricao": "Um facão enferrujado, útil para cortar cipós e lutar de perto.",
        "arma": True,
        "dano": (8, 14),
        "requer_municao": False,
    },
    "kit_medico": {
        "nome": "Kit Médico",
        "aliases": ["kit", "kit medico", "kit médico", "curativo"],
        "descricao": "Ataduras e morfina. Recupera 40 pontos de vida.",
        "cura": 40,
    },
    "lanterna": {
        "nome": "Lanterna",
        "aliases": ["lanterna", "luz"],
        "descricao": "Uma lanterna a pilha, essencial para entrar nos túneis.",
    },
    "placas": {
        "nome": "Placas de Identificação",
        "aliases": ["placas", "identificacao", "identificação", "tags"],
        "descricao": "Placas de um soldado que não teve a mesma sorte que você. Um lembrete do preço da guerra.",
    },
    "radio": {
        "nome": "Rádio Militar",
        "aliases": ["radio", "rádio"],
        "descricao": "Um rádio de campanha PRC-77, capaz de chamar o resgate.",
    },
}

ENEMIES = {
    "patrulha_vc": {
        "nome": "Patrulha Inimiga",
        "hp": 26,
        "dano": (3, 9),
        "chance_fuga": 0.55,
        "descricao": "Dois soldados inimigos surgem entre o mato, armas em punho!",
    },
    "sentinela_vc": {
        "nome": "Sentinela do Túnel",
        "hp": 22,
        "dano": (2, 8),
        "chance_fuga": 0.5,
        "descricao": "Um sentinela salta da escuridão do túnel.",
    },
    "comandante_vc": {
        "nome": "Comandante Inimigo",
        "hp": 55,
        "dano": (6, 15),
        "chance_fuga": 0.25,
        "descricao": "O comandante do acampamento aponta a arma para você. Não há como fugir com facilidade.",
        "drop": "radio",
    },
}

# room_id -> dados da sala
ROOMS = {
    "destrocos": {
        "nome": "Destroços do Helicóptero",
        "descricao": (
            "Você acorda entre os destroços retorcidos do helicóptero. Fumaça sobe por entre "
            "as árvores. Do seu pelotão, não há sinal. Ao longe, tiros e o som da selva."
        ),
        "exits": {"norte": "trilha_norte", "leste": "trilha_leste"},
        "itens": ["m16", "municao"],
    },
    "trilha_norte": {
        "nome": "Trilha da Selva - Norte",
        "descricao": (
            "Uma trilha estreita corta a vegetação densa. Cipós pendem por toda parte, "
            "e o chão esconde armadilhas de bambu."
        ),
        "exits": {"sul": "destrocos", "norte": "clareira", "oeste": "pantano"},
        "itens": ["facao"],
        "armadilha": True,
    },
    "trilha_leste": {
        "nome": "Trilha da Selva - Leste",
        "descricao": "A trilha leste desce em direção a um pântano. O ar é abafado e úmido.",
        "exits": {"oeste": "destrocos", "norte": "pantano"},
        "itens": [],
    },
    "clareira": {
        "nome": "Clareira Abandonada",
        "descricao": (
            "Uma clareira com uma fogueira apagada há dias. Ao lado das cinzas, "
            "placas de identificação brilham fracamente."
        ),
        "exits": {"sul": "trilha_norte", "leste": "vilarejo"},
        "itens": ["placas"],
    },
    "pantano": {
        "nome": "Arrozal Alagado",
        "descricao": "Um arrozal alagado se estende à sua frente. A lama dificulta cada passo.",
        "exits": {"leste": "trilha_norte", "sul": "trilha_leste", "norte": "rio"},
        "itens": [],
        "encontro": "patrulha_vc",
        "chance_encontro": 0.5,
    },
    "rio": {
        "nome": "Travessia do Rio",
        "descricao": "Um rio de correnteza forte corta o caminho. Do outro lado, um vilarejo abandonado.",
        "exits": {"sul": "pantano", "norte": "vilarejo"},
        "itens": [],
    },
    "vilarejo": {
        "nome": "Vilarejo Abandonado",
        "descricao": (
            "Casebres de madeira, portas arrombadas. Um velho aldeão ferido se esconde em um canto "
            "e aponta em silêncio para um buraco no chão, coberto por folhas: a entrada dos túneis."
        ),
        "exits": {"sul": "rio", "oeste": "clareira", "leste": "entrada_tuneis"},
        "itens": ["kit_medico", "lanterna"],
    },
    "entrada_tuneis": {
        "nome": "Entrada dos Túneis",
        "descricao": "Um buraco escuro desce para os túneis subterrâneos. Está breu lá dentro.",
        "exits": {"oeste": "vilarejo", "baixo": "tunel"},
        "itens": [],
        "requer_item_para_entrar": {"direcao": "baixo", "item": "lanterna",
                                     "mensagem": "Está escuro demais para descer sem uma fonte de luz."},
    },
    "tunel": {
        "nome": "Labirinto de Túneis",
        "descricao": (
            "Túneis estreitos serpenteiam na escuridão, iluminados apenas pela sua lanterna. "
            "O ar é pesado e o silêncio, opressivo."
        ),
        "exits": {"cima": "entrada_tuneis", "norte": "cela", "leste": "acampamento"},
        "itens": [],
        "encontro": "sentinela_vc",
        "chance_encontro": 0.5,
    },
    "cela": {
        "nome": "Cela do Prisioneiro",
        "descricao": (
            "Numa cela improvisada, o Sgt. Ramirez está acorrentado, ferido mas vivo. "
            "\"Achei que ninguém viria...\", ele sussurra."
        ),
        "exits": {"sul": "tunel"},
        "itens": [],
        "npc": "prisioneiro",
    },
    "acampamento": {
        "nome": "Acampamento Inimigo",
        "descricao": "O acampamento inimigo se abre numa clareira subterrânea iluminada por tochas.",
        "exits": {"oeste": "tunel", "norte": "posto_radio"},
        "itens": [],
        "encontro": "comandante_vc",
        "chance_encontro": 1.0,
        "bloqueio_flag": "comandante_derrotado",
        "bloqueio_direcao": "norte",
        "bloqueio_mensagem": "O comandante inimigo bloqueia a passagem para o norte.",
    },
    "posto_radio": {
        "nome": "Posto de Rádio",
        "descricao": "Uma antena improvisada e um velho rádio de campanha. Daqui talvez dê para chamar o resgate.",
        "exits": {"sul": "acampamento", "norte": "lz_extracao"},
        "itens": [],
        "requer_flag_para_entrar": {"direcao": "norte", "flag": "evac_chamado",
                                     "mensagem": "Sem contato com o resgate, seguir para o norte é ir direto para a morte. Use o rádio primeiro."},
    },
    "lz_extracao": {
        "nome": "Zona de Extração",
        "descricao": "O som do rotor de um helicóptero corta o céu. A extração chegou.",
        "exits": {},
        "itens": [],
        "final": True,
    },
}

DIRECOES_ALIASES = {
    "n": "norte", "norte": "norte",
    "s": "sul", "sul": "sul",
    "l": "leste", "leste": "leste", "e": "leste",
    "o": "oeste", "oeste": "oeste", "w": "oeste",
    "cima": "cima", "subir": "cima", "c": "cima",
    "baixo": "baixo", "descer": "baixo", "b": "baixo",
}
