"""Paleta preta, a mesma para todo card de profile/.

Os cards são fundo preto com borda grafite, então ficam iguais no tema claro e no
escuro do GitHub: no claro viram blocos pretos de propósito, no escuro se fundem
com a página. Uma paleta só, sem cor de marca: a hierarquia sai do tom de cinza.
"""

FUNDO = "#0A0A0A"       # fundo dos cards
BORDA = "#262626"       # contorno e divisórias
TRILHO = "#1C1C1C"      # trilho vazio das barras
TEXTO = "#FAFAFA"       # números e nomes
SECUNDARIO = "#A3A3A3"  # rótulos
APAGADO = "#737373"     # datas e notas
DESTAQUE = "#FFFFFF"    # anel, chama e barras cheias

FONTE = "'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

LARGURA, ALTURA = 440, 195
RAIO = 8


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def moldura(largura=LARGURA):
    """O retângulo do card. Meio pixel para dentro, senão o traço sai cortado."""
    return ('<rect x="0.5" y="0.5" width="%d" height="%d" rx="%d" fill="%s" '
            'stroke="%s"/>' % (largura - 1, ALTURA - 1, RAIO, FUNDO, BORDA))


def svg(partes, alt, defs="", largura=LARGURA):
    linhas = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
              'viewBox="0 0 %d %d" role="img" aria-label="%s">'
              % (largura, ALTURA, largura, ALTURA, esc(alt)),
              "  <title>%s</title>" % esc(alt)]
    if defs:
        linhas.append("  <defs>%s</defs>" % defs)
    linhas.append("  " + moldura(largura))
    linhas.append('  <g font-family="%s">' % FONTE)
    linhas += ["    " + p for p in partes]
    linhas += ["  </g>", "</svg>"]
    return "\n".join(linhas) + "\n"
