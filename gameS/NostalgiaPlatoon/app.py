import os

from flask import Flask, redirect, render_template, request, session, url_for
from flask_session import Session

from game.data import ROOMS
from game.engine import novo_estado, processa_comando

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nostalgia-platoon-dev-key")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.instance_path, "flask_session")
app.config["SESSION_PERMANENT"] = False
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
Session(app)


def _hud(estado: dict) -> dict:
    sala = ROOMS[estado["sala"]]
    hp_pct = max(0, round(100 * estado["hp"] / estado["hp_max"]))
    return {
        "sala_nome": sala["nome"],
        "hp": estado["hp"],
        "hp_max": estado["hp_max"],
        "hp_pct": hp_pct,
        "exits": list(sala["exits"].keys()),
        "inventario": estado["inventario"],
        "em_combate": estado["inimigo"] is not None,
        "fim": estado["fim"],
    }


@app.route("/")
def intro():
    return render_template("intro.html")


@app.route("/novo-jogo", methods=["POST"])
def novo_jogo():
    session["estado"] = novo_estado()
    return redirect(url_for("jogo"))


@app.route("/jogo")
def jogo():
    if "estado" not in session:
        return redirect(url_for("intro"))
    estado = session["estado"]
    return render_template("jogo.html", log=estado["log"], hud=_hud(estado))


@app.route("/acao", methods=["POST"])
def acao():
    if "estado" not in session:
        return redirect(url_for("intro"))
    estado = session["estado"]
    comando = request.form.get("comando", "")
    processa_comando(estado, comando)
    session["estado"] = estado
    return redirect(url_for("jogo"))


if __name__ == "__main__":
    app.run(debug=True)
