#!/usr/bin/env python3
"""Fixa e confere os endereços das imagens do README.

O GitHub serve imagem de README pelo camo, um cache no servidor dele. Duas
propriedades do camo mandam no desenho desta página:

  1. Ele obedece o max-age de quem entrega. Um card de sequência, que precisa
     dizer HOJE, atrás de um max-age longo mostra o dia anterior.
  2. Ele desiste de buscar em poucos segundos. Uma imagem calculada na hora por
     um serviço externo estoura esse tempo e some da página.

Daí as duas regras que este arquivo faz valer:

  - Todo src é ARQUIVO PARADO, servido pelo jsdelivr (nossos SVG) ou pelo
    shields (badges de status, stack e contato, que não têm dado nosso). Se um
    gerador falhar, o arquivo anterior continua no lugar e a tela mostra dado
    velho em vez de um buraco.
  - Os nossos cards vão fixados no COMMIT (@<sha>), que o jsdelivr serve como
    "immutable". Endereço novo o camo é obrigado a buscar, então o dado novo
    aparece assim que a Action roda, sem esperar cache nenhum expirar.

E nunca aponte para raw.githubusercontent.com nem para caminho relativo (que o
GitHub reescreve para lá): o raw não passa pelo camo, então quem busca é o
navegador de quem visita, e ele leva 429 por IP.

Dois modos, os dois usados pelo .github/workflows/cards.yml:
    --verificar       guarda: reprova host de fora, raw, relativo e pino faltando
    --fixar <sha>     troca o pino dos nossos cards
"""

import argparse
import os
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
README = RAIZ / "README.md"

# O repositório vem da própria Action (GITHUB_REPOSITORY = "dono/repo"). Assim o
# README se liga sozinho à conta onde for publicado: o --fixar reescreve dono,
# repo e pino de uma vez, e ninguém precisa editar nome de usuário à mão.
REPO = os.environ.get("GITHUB_REPOSITORY") or "jcx3r/jcx3r"

# Os nossos cards (capa, linguagens, sequência), servidos pelo jsdelivr a
# partir de um commit.
NOSSO = re.compile(
    r"https://cdn\.jsdelivr\.net/gh/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@"
    r"([^/\s\"]+)"
    r"(/profile/[a-z-]+\.svg)"
)
PINO = re.compile(r"^[0-9a-f]{40}$")

# Só estes hosts entregam imagem para esta página. A lista é curta de propósito:
# cada host novo é uma peça a mais que pode cair no meio da tela de alguém.
HOSTS = ("cdn.jsdelivr.net", "img.shields.io")

# Contamos os src para que uma varredura muda não passe por aprovação. 3 são os
# nossos (capa, linguagens, sequência); o resto pode mudar sem esbarrar aqui.
MINIMO_SRC = 3


def srcs(texto):
    """Só os src, nunca o arquivo todo: o próprio README explica em comentário
    por que o raw não serve, e varrer o texto reprovaria a explicação."""
    return re.findall(r'src="([^"]*)"', texto)


def host(s):
    m = re.match(r"https?://([^/]+)/", s)
    return m.group(1) if m else None


def verificar(texto):
    """Devolve a lista de motivos de reprova. Vazia significa aprovado."""
    ruins = []
    achados = srcs(texto)

    # Amostra vazia é reprova, não aprovação: guarda que não vê nada passa verde.
    if len(achados) < MINIMO_SRC:
        ruins.append("poucos src encontrados (%d); a varredura não está vendo o README"
                     % len(achados))

    pinos = set()
    for s in achados:
        if s.startswith("data:"):
            continue  # imagem embutida; não vai à rede
        if "raw.githubusercontent.com" in s:
            ruins.append("src aponta para raw.githubusercontent.com: %s" % s[:70])
            continue
        if s.startswith("/") or s.startswith("./") or s.startswith("../"):
            ruins.append("src relativo; o GitHub o reescreve para o raw: %s" % s[:70])
            continue

        h = host(s)
        if h not in HOSTS:
            ruins.append(
                "src em host que não entrega arquivo parado (%s); o camo desiste em ~4s "
                "e o card some: %s" % (h, s[:60]))
            continue

        m = NOSSO.search(s)
        if m:
            if not PINO.match(m.group(2)):
                ruins.append("card nosso sem pino de commit (achei %r): %s"
                             % (m.group(2), s[:60]))
            else:
                pinos.add(m.group(2))

    # Pinos diferentes significam rewrite pela metade, com meia tela velha.
    if len(pinos) > 1:
        ruins.append("pinos divergentes nos nossos cards: %s" % ", ".join(sorted(pinos)))
    if not pinos:
        ruins.append("nenhum card nosso fixado; nada obrigaria o camo a buscar de novo")
    return ruins


def fixar(texto, sha):
    if not PINO.match(sha):
        raise SystemExit("pino tem de ser um sha de 40 hex, recebi %r" % sha)
    return NOSSO.sub(lambda m: "https://cdn.jsdelivr.net/gh/%s@%s%s" % (REPO, sha, m.group(3)), texto)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--verificar", action="store_true")
    p.add_argument("--fixar", metavar="SHA")
    a = p.parse_args()

    texto = README.read_text()

    if a.fixar:
        novo = fixar(texto, a.fixar)
        ruins = verificar(novo)
        if ruins:
            # Nunca gravar um README que a própria guarda reprova.
            for r in ruins:
                print("ERRO apos fixar: %s" % r, file=sys.stderr)
            return 1
        if novo == texto:
            print("pino já era %s, nada a escrever" % a.fixar[:8])
            return 0
        README.write_text(novo)
        print("pino trocado para %s" % a.fixar[:8])
        return 0

    if a.verificar:
        ruins = verificar(texto)
        for r in ruins:
            print("::error::%s" % r)
        if ruins:
            return 1
        print("aprovado: %d src, todos arquivo parado, nossos cards fixados"
              % len(srcs(texto)))
        return 0

    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
