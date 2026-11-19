#!/usr/bin/env python3
"""Gera profile/sequencia.svg: total de contribuições, sequência atual e maior.

O card é um ARQUIVO no repo, como o de linguagens, em vez de uma imagem que um
serviço externo calcula a cada visita. O jsdelivr serve em milissegundos, o
camo do GitHub nunca estoura o tempo, e se este script falhar o arquivo
anterior continua no lugar: a tela mostra um dado velho, nunca um buraco.

Uso:
    GH_TOKEN=... python3 scripts/gerar-sequencia.py [--saida profile/sequencia.svg]
    python3 scripts/gerar-sequencia.py --vazio     # card de espera, sem rede

Sem token válido ou sem rede, ele sai com código 1 e NÃO toca o arquivo.
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

from paleta import (ALTURA, APAGADO, BORDA, DESTAQUE, LARGURA, SECUNDARIO,
                    TEXTO, esc, svg)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# O dono do repositório, que a Action entrega em GITHUB_REPOSITORY_OWNER: os
# números são sempre da conta onde o repo está. Fora da Action vale o padrão.
USUARIO = os.environ.get("GITHUB_REPOSITORY_OWNER") or "jcx3r"

# São Paulo, fixo em -3. O Brasil não tem horário de verão desde 2019, e cravar
# o offset evita depender do tzdata da máquina que roda a Action. A regra:
# data de calendário tem fuso, e o fuso é o da PESSOA, nunca o
# do processo. Em UTC, um commit das 22h de São Paulo cairia no dia seguinte e
# a sequência contaria um dia que ainda não aconteceu.
FUSO = dt.timezone(dt.timedelta(hours=-3))

MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# As cores saem de paleta.py, a mesma de todo card de profile/.

CONSULTA = """
query($login: String!, $de: DateTime!, $ate: DateTime!) {
  user(login: $login) {
    createdAt
    contributionsCollection(from: $de, to: $ate) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
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
    """Devolve {data: contagem} desde a criação da conta até hoje.

    A API só entrega um ano por chamada, então o intervalo é fatiado. Fatia que
    volta vazia é erro, não zero: um recorte mudo viraria sequência zerada.
    """
    hoje = dt.datetime.now(FUSO).date()
    d = graphql(token, {
        "login": USUARIO,
        "de": "%sT00:00:00Z" % (hoje - dt.timedelta(days=1)),
        "ate": "%sT23:59:59Z" % hoje,
    })
    criada = dt.datetime.strptime(d["user"]["createdAt"][:10], "%Y-%m-%d").date()

    dias = {}
    inicio = criada
    while inicio <= hoje:
        fim = min(inicio + dt.timedelta(days=364), hoje)
        d = graphql(token, {
            "login": USUARIO,
            "de": "%sT00:00:00Z" % inicio,
            "ate": "%sT23:59:59Z" % fim,
        })
        cal = d["user"]["contributionsCollection"]["contributionCalendar"]
        achou = 0
        for semana in cal["weeks"]:
            for dia in semana["contributionDays"]:
                data = dt.datetime.strptime(dia["date"], "%Y-%m-%d").date()
                if criada <= data <= hoje:
                    dias[data] = dia["contributionCount"]
                    achou += 1
        if achou == 0:
            raise RuntimeError("fatia %s..%s voltou sem dia nenhum" % (inicio, fim))
        inicio = fim + dt.timedelta(days=1)
    return criada, hoje, dias


def contar(criada, hoje, dias):
    total = sum(dias.values())

    # Maior sequência: a maior corrida de dias consecutivos com contribuição.
    maior = (0, None, None)
    corrida, comeco = 0, None
    data = criada
    while data <= hoje:
        if dias.get(data, 0) > 0:
            corrida += 1
            if comeco is None:
                comeco = data
            if corrida > maior[0]:
                maior = (corrida, comeco, data)
        else:
            corrida, comeco = 0, None
        data += dt.timedelta(days=1)

    # Sequência atual: a corrida que termina hoje. Se hoje ainda está zerado, o
    # dia NÃO acabou, então a corrida que termina ontem continua valendo. Sem
    # essa carência a sequência zeraria toda madrugada e voltaria à tarde.
    fim = hoje if dias.get(hoje, 0) > 0 else hoje - dt.timedelta(days=1)
    if dias.get(fim, 0) == 0:
        atual = (0, None, None)
    else:
        comeco = fim
        while comeco > criada and dias.get(comeco - dt.timedelta(days=1), 0) > 0:
            comeco -= dt.timedelta(days=1)
        atual = ((fim - comeco).days + 1, comeco, fim)

    return {"total": total, "atual": atual, "maior": maior}


def numero(n):
    """2654 -> "2,654". O README é em inglês, então o separador é a vírgula."""
    return "-" if n is None else "{:,}".format(n)


def data_curta(d):
    return "%s %d" % (MESES[d.month - 1], d.day)


def periodo(a, b, aberto=False):
    """"Apr 1 - Present" só para o total, que não tem fim. Para as
    sequências o fim é uma DATA: dizer "Present" numa sequência esconde
    justamente o dado que a pessoa foi conferir."""
    if a is None:
        return "-"
    if aberto:
        return "%s - Present" % data_curta(a)
    return "%s - %s" % (data_curta(a), data_curta(b))


# Colunas em width/6, width/2 e 5*width/6, texto ancorado no meio.
CX = (LARGURA / 6.0, LARGURA / 2.0, LARGURA * 5 / 6.0)
BASE_NUM, BASE_ROT, BASE_DATA = 80, 116, 146     # colunas das pontas
BASE_ROT_MEIO, BASE_DATA_MEIO = 140, 177         # a do meio desce por causa do anel
ANEL_CY, ANEL_R = 71, 40


def texto(cx, y, conteudo, tamanho, peso, cor):
    return ('<text x="%.2f" y="%d" text-anchor="middle" font-size="%dpx" '
            'font-weight="%d" fill="%s">%s</text>'
            % (cx, y, tamanho, peso, cor, esc(conteudo)))


def montar_svg(c, hoje):
    atual_n, atual_a, atual_b = c["atual"]
    maior_n, maior_a, maior_b = c["maior"]

    # A chama vai por path, nunca por emoji: emoji dentro de SVG servido pelo
    # camo cai na fonte que a máquina de quem visita tiver, e some em muitas.
    chama = ('<path transform="translate(%.2f 32)" fill="%s" '
             'd="M0,-18 C6,-10 12,-4 12,3 C12,10 6,16 0,16 C-6,16 -12,10 -12,3 '
             'C-12,-3 -8,-9 -4.5,-12 C-4.8,-6 -3,-3 0,-3 C2.8,-3 4,-6 3,-10 '
             'C2.2,-13 1,-15.6 0,-18 Z"/>' % (CX[1], DESTAQUE))

    # O anel é cortado onde a chama pousa, senão a linha atravessa o desenho.
    mascara = ('<mask id="corte"><rect width="%d" height="%d" fill="white"/>'
               '<ellipse cx="%.2f" cy="32" rx="15" ry="20" fill="black"/></mask>'
               % (LARGURA, ALTURA, CX[1]))
    anel = ('<circle cx="%.2f" cy="%d" r="%d" fill="none" stroke="%s" '
            'stroke-width="4" mask="url(#corte)"/>'
            % (CX[1], ANEL_CY, ANEL_R, DESTAQUE))

    partes = [anel, chama]

    # Ponta esquerda: o total, que não tem fim. Ponta direita: o recorde.
    for cx, valor, rotulo, faixa in (
        (CX[0], numero(c["total"]), "Total Contributions",
         periodo(c["criada"], hoje, aberto=True)),
        (CX[2], numero(maior_n), "Longest Streak", periodo(maior_a, maior_b)),
    ):
        partes.append(texto(cx, BASE_NUM, valor, 28, 700, TEXTO))
        partes.append(texto(cx, BASE_ROT, rotulo, 14, 400, SECUNDARIO))
        partes.append(texto(cx, BASE_DATA, faixa, 12, 400, APAGADO))

    # Meio: a sequência de agora, o único rótulo em branco cheio.
    partes.append(texto(CX[1], BASE_NUM, numero(atual_n), 28, 700, TEXTO))
    partes.append(texto(CX[1], BASE_ROT_MEIO, "Current Streak", 14, 700, TEXTO))
    partes.append(texto(CX[1], BASE_DATA_MEIO, periodo(atual_a, atual_b), 12, 400, APAGADO))

    for x in (LARGURA / 3.0, LARGURA * 2 / 3.0):
        partes.append('<line x1="%.2f" y1="28" x2="%.2f" y2="170" stroke="%s" '
                      'stroke-width="1"/>' % (x, x, BORDA))

    if c["total"] is None:
        alt = "Contribution streak: waiting for the first sync"
    else:
        alt = ("Contribution streak: %s total, %d days in a row now, %d at most"
               % (numero(c["total"]), atual_n, maior_n))
    return svg(partes, alt, defs=mascara)


def card_vazio():
    """O card de antes da primeira coleta: mesma moldura, traço no lugar de
    número. Zero seria um dado inventado; traço diz "ainda não sei"."""
    vazio = (None, None, None)
    return montar_svg({"total": None, "atual": vazio, "maior": vazio,
                       "criada": None}, None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--saida", default=str(RAIZ / "profile" / "sequencia.svg"))
    p.add_argument("--json", action="store_true", help="só imprime os números")
    p.add_argument("--vazio", action="store_true",
                   help="grava o card de espera, sem tocar na rede")
    a = p.parse_args()

    if a.vazio:
        pathlib.Path(a.saida).write_text(card_vazio(), encoding="utf-8")
        print("sequencia.svg: card de espera")
        return 0

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("::error::sem GH_TOKEN; o arquivo anterior fica como está", file=sys.stderr)
        return 1

    try:
        criada, hoje, dias = colher(token)
    except (urllib.error.URLError, RuntimeError, KeyError, TypeError, ValueError) as e:
        # Falhar aqui é seguro de propósito: sem escrita, o card de ontem
        # continua na tela. Buraco na página é o único desfecho inaceitável.
        print("::warning::não deu para colher as contribuições (%s); "
              "mantendo o card anterior" % e, file=sys.stderr)
        return 1

    c = contar(criada, hoje, dias)
    c["criada"] = criada

    if a.json:
        print(json.dumps({
            "total": c["total"],
            "atual": [c["atual"][0], str(c["atual"][1]), str(c["atual"][2])],
            "maior": [c["maior"][0], str(c["maior"][1]), str(c["maior"][2])],
            "criada": str(criada), "hoje": str(hoje),
        }, ensure_ascii=False))
        return 0

    pathlib.Path(a.saida).write_text(montar_svg(c, hoje), encoding="utf-8")
    print("sequencia.svg: total %s, atual %d, maior %d"
          % (numero(c["total"]), c["atual"][0], c["maior"][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
