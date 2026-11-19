#!/usr/bin/env python3
"""Gera profile/langs.svg: as linguagens mais usadas, em preto e branco.

Por que não o card pronto do github-readme-stats. Ele pinta cada linguagem com a
cor dela (amarelo do JavaScript, azul do TypeScript...), e a página é preta e
branca. Aqui a barra é sempre branca e o que muda é o comprimento, então o card
se lê sem depender de cor nenhuma.

Mesma regra dos outros cards: o resultado é ARQUIVO no repo, servido pelo
jsdelivr. Se este script falhar, o arquivo anterior continua na tela.

Uso:
    GH_TOKEN=... python3 scripts/gerar-linguagens.py [--saida profile/langs.svg]
    python3 scripts/gerar-linguagens.py --vazio     # card de espera, sem rede

Com um PAT (GRS_TOKEN) entram os repositórios privados; com o GITHUB_TOKEN da
Action, só os públicos.
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

from paleta import (ALTURA, APAGADO, DESTAQUE, MONO, SECUNDARIO, TEXTO,
                    TRILHO, esc, svg)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
USUARIO = os.environ.get("GITHUB_REPOSITORY_OWNER") or "jcx3r"

QUANTAS = 6

# Mais estreito que o card de sequência (440): os dois lado a lado na altura
# 190 do README somam ~780px e cabem na coluna do perfil. Com 440 cada, o
# segundo quebra para baixo.
LARGURA = 340
NOME_MAX = 14

# Linguagens que são cola, não trabalho: um repo com Makefile ou Dockerfile não
# deveria aparecer no card como se fosse a stack da pessoa.
IGNORAR = {"Dockerfile", "Makefile", "Shell", "Batchfile", "PowerShell",
           "Procfile", "Nix"}

CONSULTA = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def graphql(token, variaveis):
    corpo = json.dumps({"query": CONSULTA, "variables": variaveis}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=corpo,
        headers={
            "Authorization": "bearer %s" % token,
            "Content-Type": "application/json",
            "User-Agent": "profile-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        dados = json.loads(r.read().decode())
    if "errors" in dados:
        raise RuntimeError("GraphQL: %s" % dados["errors"])
    return dados["data"]


def colher(token):
    """Soma os bytes por linguagem em todos os repos da conta.

    O repo do próprio perfil fica de fora: ele é só a máquina destes cards, e
    contaria Python para quem talvez nem use Python.
    """
    somas, cursor = {}, None
    while True:
        d = graphql(token, {"login": USUARIO, "cursor": cursor})
        repos = d["user"]["repositories"]
        for repo in repos["nodes"]:
            if repo["name"].lower() == USUARIO.lower():
                continue
            for e in repo["languages"]["edges"]:
                nome = e["node"]["name"]
                if nome not in IGNORAR:
                    somas[nome] = somas.get(nome, 0) + e["size"]
        if not repos["pageInfo"]["hasNextPage"]:
            return somas
        cursor = repos["pageInfo"]["endCursor"]


def montar_svg(somas):
    total = sum(somas.values())
    topo = sorted(somas.items(), key=lambda kv: -kv[1])[:QUANTAS]

    partes = [
        '<text x="24" y="38" font-size="15px" font-weight="700" fill="%s">'
        'Most used languages</text>' % TEXTO,
    ]

    if not topo:
        # Conta sem código ainda: um card de espera, nunca um buraco.
        for i, linha in enumerate(("First sync pending.",
                                   "This card updates every 6 hours.")):
            partes.append('<text x="24" y="%d" font-size="13px" fill="%s">%s</text>'
                          % (ALTURA // 2 + 4 + 20 * i, APAGADO, linha))
        return svg(partes, "Most used languages: waiting for the first sync",
                   largura=LARGURA)

    # Linhas de 22px a partir do título; a barra mede a parte de cada uma.
    x_nome, x_barra, x_pct = 24, 132, LARGURA - 24
    largura_barra = x_pct - 56 - x_barra
    y = 68
    for nome, bytes_ in topo:
        parte = bytes_ / total
        cheio = max(6.0, largura_barra * parte)
        # Nome comprido ("Jupyter Notebook") encostaria na barra: corta com "…".
        curto = nome if len(nome) <= NOME_MAX else nome[:NOME_MAX - 1] + "…"
        partes.append('<text x="%d" y="%d" font-size="13px" fill="%s">%s</text>'
                      % (x_nome, y, TEXTO, esc(curto)))
        partes.append('<rect x="%d" y="%d" width="%d" height="6" rx="3" fill="%s"/>'
                      % (x_barra, y - 7, largura_barra, TRILHO))
        partes.append('<rect x="%d" y="%d" width="%.1f" height="6" rx="3" fill="%s"/>'
                      % (x_barra, y - 7, cheio, DESTAQUE))
        partes.append('<text x="%d" y="%d" text-anchor="end" font-size="12px" '
                      'font-family="%s" fill="%s">%.1f%%</text>'
                      % (x_pct, y, MONO, SECUNDARIO, parte * 100))
        y += 22

    alt = "Most used languages: " + ", ".join(
        "%s %.0f%%" % (n, b * 100.0 / total) for n, b in topo)
    return svg(partes, alt, largura=LARGURA)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--saida", default=str(RAIZ / "profile" / "langs.svg"))
    p.add_argument("--vazio", action="store_true",
                   help="grava o card de espera, sem tocar na rede")
    a = p.parse_args()

    if a.vazio:
        pathlib.Path(a.saida).write_text(montar_svg({}), encoding="utf-8")
        print("langs.svg: card de espera")
        return 0

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("::error::sem GH_TOKEN; o arquivo anterior fica como está", file=sys.stderr)
        return 1

    try:
        somas = colher(token)
    except (urllib.error.URLError, RuntimeError, KeyError, TypeError, ValueError) as e:
        print("::warning::não deu para colher as linguagens (%s); "
              "mantendo o card anterior" % e, file=sys.stderr)
        return 1

    pathlib.Path(a.saida).write_text(montar_svg(somas), encoding="utf-8")
    print("langs.svg: %d linguagens" % min(len(somas), QUANTAS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
