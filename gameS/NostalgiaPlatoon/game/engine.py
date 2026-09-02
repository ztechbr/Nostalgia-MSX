"""Motor de jogo: estado, parser de comandos e regras (combate, itens, mapa)."""
import random
import unicodedata

from .data import ROOMS, ITEMS, ENEMIES, DIRECOES_ALIASES

MAX_LOG = 60
HP_INICIAL = 100


def _sem_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normaliza(texto: str) -> str:
    return _sem_acentos(texto).strip().lower()


def novo_estado() -> dict:
    itens_por_sala = {rid: list(sala.get("itens", [])) for rid, sala in ROOMS.items()}
    estado = {
        "sala": "destrocos",
        "sala_anterior": "destrocos",
        "hp": HP_INICIAL,
        "hp_max": HP_INICIAL,
        "inventario": [],
        "flags": {},
        "itens_por_sala": itens_por_sala,
        "inimigo": None,
        "log": [],
        "fim": None,
    }
    _log(estado, "*** NOSTALGIA PLATOON ***")
    _log(estado, "Selva. 1968. Você é o único sobrevivente do seu pelotão após a emboscada.")
    _log(estado, "Encontre um jeito de chegar à zona de extração com vida.")
    _log(estado, "Digite 'ajuda' a qualquer momento para ver os comandos.")
    _log(estado, "")
    _descrever_sala(estado, primeira_vez=True)
    return estado


def _log(estado: dict, mensagem: str):
    estado["log"].append(mensagem)
    if len(estado["log"]) > MAX_LOG:
        estado["log"] = estado["log"][-MAX_LOG:]


def resolve_item(alias: str):
    alias = normaliza(alias)
    for item_id, dados in ITEMS.items():
        nomes = [normaliza(a) for a in dados["aliases"]] + [normaliza(dados["nome"])]
        if alias in nomes:
            return item_id
    return None


def _nome_item(item_id: str) -> str:
    return ITEMS[item_id]["nome"]


def _descrever_sala(estado: dict, primeira_vez=False):
    sala = ROOMS[estado["sala"]]
    _log(estado, f"== {sala['nome']} ==")
    _log(estado, sala["descricao"])

    itens_aqui = estado["itens_por_sala"].get(estado["sala"], [])
    if itens_aqui:
        nomes = ", ".join(_nome_item(i) for i in itens_aqui)
        _log(estado, f"Você vê aqui: {nomes}.")

    if sala.get("npc") == "prisioneiro" and not estado["flags"].get("prisioneiro_resgatado"):
        _log(estado, "O Sgt. Ramirez está preso aqui. Fale com ele.")
    if estado["sala"] == "vilarejo" and not estado["flags"].get("aldeao_falou"):
        _log(estado, "Um aldeão ferido observa você em silêncio. Talvez ele saiba de algo.")

    saidas = ", ".join(sala["exits"].keys()) if sala["exits"] else "nenhuma"
    _log(estado, f"Saídas: {saidas}.")


def _arma_equipada(estado: dict):
    inv = estado["inventario"]
    if "m16" in inv and "municao" in inv:
        return "m16", ITEMS["m16"]["dano"]
    if "facao" in inv:
        return "facao", ITEMS["facao"]["dano"]
    return None, (5, 10)


def _bonus_aliado(estado: dict) -> int:
    return 5 if estado["flags"].get("aliado") else 0


def _iniciar_combate(estado: dict, enemy_id: str):
    base = ENEMIES[enemy_id]
    estado["inimigo"] = {"id": enemy_id, "hp": base["hp"]}
    _log(estado, f">> {base['descricao']}")


def _talvez_encontro(estado: dict):
    sala = ROOMS[estado["sala"]]
    enemy_id = sala.get("encontro")
    if not enemy_id or estado["inimigo"] is not None:
        return
    if estado["sala"] == "acampamento" and estado["flags"].get("comandante_derrotado"):
        return
    chance = sala.get("chance_encontro", 0)
    if random.random() < chance:
        _iniciar_combate(estado, enemy_id)


def mover(estado: dict, direcao_raw: str):
    if estado["fim"]:
        _log(estado, "A missão terminou. Inicie um novo jogo para jogar de novo.")
        return
    if estado["inimigo"]:
        _log(estado, "Você está em combate! Não há tempo para fugir andando -- use 'atacar' ou 'fugir'.")
        return

    direcao = DIRECOES_ALIASES.get(normaliza(direcao_raw))
    if not direcao:
        _log(estado, "Direção desconhecida. Use: norte, sul, leste, oeste, cima ou baixo.")
        return

    sala = ROOMS[estado["sala"]]

    bloqueio_dir = sala.get("bloqueio_direcao")
    if bloqueio_dir == direcao and not estado["flags"].get(sala.get("bloqueio_flag"), False):
        _log(estado, sala.get("bloqueio_mensagem", "O caminho está bloqueado."))
        _iniciar_combate(estado, sala["encontro"])
        return

    if direcao not in sala["exits"]:
        _log(estado, "Não há caminho nessa direção.")
        return

    req_item = sala.get("requer_item_para_entrar")
    if req_item and req_item["direcao"] == direcao and req_item["item"] not in estado["inventario"]:
        _log(estado, req_item["mensagem"])
        return

    req_flag = sala.get("requer_flag_para_entrar")
    if req_flag and req_flag["direcao"] == direcao and not estado["flags"].get(req_flag["flag"]):
        _log(estado, req_flag["mensagem"])
        return

    destino = sala["exits"][direcao]
    if sala.get("armadilha") and not estado["flags"].get("armadilha_" + estado["sala"]):
        estado["flags"]["armadilha_" + estado["sala"]] = True
        if "facao" not in estado["inventario"]:
            dano = random.randint(6, 15)
            estado["hp"] -= dano
            _log(estado, f"Uma armadilha de bambu escondida na trilha te pega! Você perde {dano} de vida.")
            if estado["hp"] <= 0:
                _morrer(estado, "Você sangra até a morte, sozinho na selva.")
                return
        else:
            _log(estado, "Com o facão, você corta os cipós e evita uma armadilha escondida.")

    estado["sala_anterior"] = estado["sala"]
    estado["sala"] = destino
    _log(estado, "")
    _descrever_sala(estado)

    if ROOMS[destino].get("final"):
        _vencer(estado)
        return

    _talvez_encontro(estado)


def olhar(estado: dict):
    if estado["inimigo"]:
        inimigo = ENEMIES[estado["inimigo"]["id"]]
        _log(estado, f"{inimigo['nome']} -- HP: {estado['inimigo']['hp']}/{inimigo['hp']}")
        return
    _descrever_sala(estado)


def pegar(estado: dict, alias: str):
    if not alias:
        _log(estado, "Pegar o quê?")
        return
    item_id = resolve_item(alias)
    itens_aqui = estado["itens_por_sala"].get(estado["sala"], [])
    if not item_id or item_id not in itens_aqui:
        _log(estado, "Não há isso aqui.")
        return
    itens_aqui.remove(item_id)
    estado["inventario"].append(item_id)
    _log(estado, f"Você pega: {_nome_item(item_id)}.")


def usar(estado: dict, alias: str):
    if not alias:
        _log(estado, "Usar o quê?")
        return
    item_id = resolve_item(alias)
    if not item_id or item_id not in estado["inventario"]:
        _log(estado, "Você não tem isso.")
        return

    if item_id == "kit_medico":
        cura = ITEMS["kit_medico"]["cura"]
        estado["hp"] = min(estado["hp_max"], estado["hp"] + cura)
        estado["inventario"].remove(item_id)
        _log(estado, f"Você usa o kit médico e recupera vida. HP: {estado['hp']}/{estado['hp_max']}.")
        return

    if item_id == "radio":
        if estado["sala"] != "posto_radio":
            _log(estado, "Sem sinal aqui. Talvez em algum posto de comunicação.")
            return
        estado["flags"]["evac_chamado"] = True
        _log(estado, "Você chama o resgate pelo rádio: \"Aqui é Cobra-2, solicito extração imediata!\"")
        _log(estado, "Uma voz responde entre estática: \"Entendido, Cobra-2. Vá para a zona de extração ao norte.\"")
        return

    if item_id == "lanterna":
        _log(estado, "Você já está com a lanterna em mãos, pronta para iluminar lugares escuros.")
        return

    if item_id in ("m16", "facao"):
        _log(estado, f"Você empunha {_nome_item(item_id)}, pronto para o confronto.")
        return

    _log(estado, f"Você examina {_nome_item(item_id)}. {ITEMS[item_id]['descricao']}")


def falar(estado: dict):
    sala_id = estado["sala"]
    sala = ROOMS[sala_id]

    if sala.get("npc") == "prisioneiro":
        if estado["flags"].get("prisioneiro_resgatado"):
            _log(estado, "Ramirez: \"Vamos sair daqui vivos, soldado.\"")
            return
        estado["flags"]["prisioneiro_resgatado"] = True
        estado["flags"]["aliado"] = True
        estado["hp_max"] += 10
        estado["hp"] += 10
        _log(estado, "Você arrebenta as correntes de Ramirez. Ele está fraco, mas vai lutar ao seu lado.")
        _log(estado, "(+10 HP máximo, e Ramirez agora ajuda nos combates.)")
        return

    if sala_id == "vilarejo":
        estado["flags"]["aldeao_falou"] = True
        _log(estado, "O aldeão aponta para o buraco coberto de folhas e sussurra: \"Túneis... inimigos... "
                     "e um homem preso lá embaixo. Levem uma luz.\"")
        return

    _log(estado, "Não há ninguém aqui para conversar.")


def atacar(estado: dict):
    if not estado["inimigo"]:
        _log(estado, "Não há ninguém para atacar aqui.")
        return

    inimigo_id = estado["inimigo"]["id"]
    inimigo_base = ENEMIES[inimigo_id]

    arma_id, dano_range = _arma_equipada(estado)
    dano = random.randint(*dano_range) + _bonus_aliado(estado)
    estado["inimigo"]["hp"] -= dano

    arma_nome = _nome_item(arma_id) if arma_id else "seus punhos"
    _log(estado, f"Você ataca com {arma_nome} e causa {dano} de dano ao {inimigo_base['nome']}.")

    if estado["inimigo"]["hp"] <= 0:
        _log(estado, f"Você derrotou: {inimigo_base['nome']}!")
        drop = inimigo_base.get("drop")
        if drop:
            estado["inventario"].append(drop)
            _log(estado, f"O inimigo derruba: {_nome_item(drop)}.")
        if inimigo_id == "comandante_vc":
            estado["flags"]["comandante_derrotado"] = True
        estado["inimigo"] = None
        return

    dano_inimigo = random.randint(*inimigo_base["dano"])
    estado["hp"] -= dano_inimigo
    _log(estado, f"{inimigo_base['nome']} revida e causa {dano_inimigo} de dano a você. HP: {estado['hp']}/{estado['hp_max']}.")

    if estado["hp"] <= 0:
        _morrer(estado, f"Você cai sob o fogo de {inimigo_base['nome'].lower()}.")


def fugir(estado: dict):
    if not estado["inimigo"]:
        _log(estado, "Não há de onde fugir agora.")
        return
    inimigo_base = ENEMIES[estado["inimigo"]["id"]]
    if random.random() < inimigo_base["chance_fuga"]:
        estado["inimigo"] = None
        estado["sala"] = estado["sala_anterior"]
        _log(estado, "Você foge de volta, o coração disparado.")
        _descrever_sala(estado)
        return
    dano_inimigo = random.randint(*inimigo_base["dano"])
    estado["hp"] -= dano_inimigo
    _log(estado, f"Você tenta fugir, mas {inimigo_base['nome'].lower()} corta sua saída e acerta {dano_inimigo} de dano.")
    if estado["hp"] <= 0:
        _morrer(estado, f"Você cai tentando fugir de {inimigo_base['nome'].lower()}.")


def status(estado: dict):
    arma_id, _ = _arma_equipada(estado)
    arma_nome = _nome_item(arma_id) if arma_id else "nenhuma (desarmado)"
    _log(estado, f"HP: {estado['hp']}/{estado['hp_max']} | Arma: {arma_nome}")
    if estado["flags"].get("aliado"):
        _log(estado, "Ramirez está lutando ao seu lado.")


def inventario(estado: dict):
    if not estado["inventario"]:
        _log(estado, "Seu inventário está vazio.")
        return
    linhas = ", ".join(_nome_item(i) for i in estado["inventario"])
    _log(estado, f"Inventário: {linhas}.")


def ajuda(estado: dict):
    _log(estado, "Comandos: norte/sul/leste/oeste/cima/baixo, olhar, pegar <item>, usar <item>,")
    _log(estado, "inventario, falar, atacar, fugir, status, ajuda.")


def _morrer(estado: dict, motivo: str):
    estado["fim"] = "derrota"
    _log(estado, "")
    _log(estado, "*** VOCÊ MORREU ***")
    _log(estado, motivo)
    _log(estado, "Fim de jogo. Inicie uma nova missão para tentar novamente.")


def _vencer(estado: dict):
    estado["fim"] = "vitoria"
    _log(estado, "")
    _log(estado, "*** MISSÃO CUMPRIDA ***")
    if estado["flags"].get("prisioneiro_resgatado"):
        _log(estado, "Você e o Sgt. Ramirez embarcam juntos no helicóptero. Ninguém fica para trás.")
    else:
        _log(estado, "Você embarca sozinho no helicóptero, deixando a selva -- e seus fantasmas -- para trás.")
    _log(estado, "Obrigado por jogar NOSTALGIA PLATOON.")


COMANDOS_SIMPLES = {
    "olhar": olhar, "ver": olhar, "look": olhar, "l": olhar,
    "inventario": inventario, "inventário": inventario, "inv": inventario, "i": inventario,
    "atacar": atacar, "lutar": atacar, "atirar": atacar,
    "fugir": fugir, "correr": fugir,
    "status": status, "vida": status, "hp": status,
    "ajuda": ajuda, "help": ajuda, "?": ajuda,
    "falar": falar, "conversar": falar,
}


def processa_comando(estado: dict, texto: str):
    texto = (texto or "").strip()
    if not texto:
        return
    partes = texto.split(maxsplit=1)
    verbo = normaliza(partes[0])
    resto = partes[1] if len(partes) > 1 else ""

    _log(estado, f"> {texto}")

    if verbo in DIRECOES_ALIASES:
        mover(estado, verbo)
        return
    if verbo in ("ir", "mover", "andar") and resto:
        mover(estado, resto)
        return
    if verbo in ("pegar", "pegue", "take", "apanhar") :
        pegar(estado, resto)
        return
    if verbo in ("usar", "use"):
        usar(estado, resto)
        return
    if verbo in COMANDOS_SIMPLES:
        COMANDOS_SIMPLES[verbo](estado)
        return

    _log(estado, "Não entendi. Digite 'ajuda' para ver os comandos disponíveis.")
