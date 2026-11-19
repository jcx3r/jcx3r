#!/usr/bin/env bash
# Publica este perfil no GitHub com um comando:
#
#     bash publicar.sh
#
# Precisa só do git. Com o GitHub CLI (gh) logado, ele cria o repositório
# sozinho e acompanha a primeira rodada da Action; sem o gh, ele diz o que criar
# no site e espera um Enter. Depois do push, a Action gera os cards e fixa o
# README sem mais nada a fazer.
#
# Opções:
#     bash publicar.sh --forcar        sobrescreve um repositório que já tem commits
#     REMOTO=git@github.com:u/u.git bash publicar.sh   usa outro endereço (SSH, por ex.)

set -euo pipefail
cd "$(dirname "$0")"

PERFIL="jcx3r"          # a conta para a qual este README foi montado
FORCAR=0
[ "${1:-}" = "--forcar" ] && FORCAR=1

passo() { printf '\n\033[1m%s\033[0m\n' "$*"; }
erro()  { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

command -v git >/dev/null || erro "Instale o git primeiro: https://git-scm.com/downloads"

# O gh só conta se estiver logado; sem login ele não serve para criar o repo.
GH=0
if [ -z "${REMOTO:-}" ] && command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  GH=1
fi

USUARIO="$PERFIL"
if [ "$GH" = 1 ]; then
  USUARIO=$(gh api user -q .login)
  if [ "$USUARIO" != "$PERFIL" ]; then
    printf 'Este perfil foi montado para "%s", mas o gh está logado como "%s".\n' "$PERFIL" "$USUARIO"
    read -r -p "Publicar mesmo assim em $USUARIO/$USUARIO? [s/N] " r
    [ "$r" = "s" ] || [ "$r" = "S" ] || erro "Nada foi publicado."
  fi
fi

# O README de perfil só aparece num repositório PÚBLICO com o mesmo nome da conta.
REPO="$USUARIO/$USUARIO"
URL="${REMOTO:-https://github.com/$REPO.git}"

passo "1/3  Preparando os arquivos"
if [ ! -d .git ]; then
  git init -q
  git symbolic-ref HEAD refs/heads/main
fi
# Sem identidade no git, o commit falha. Usa o e-mail noreply da conta, que conta
# a contribuição para ela sem expor e-mail pessoal.
if [ -z "$(git config user.email || true)" ]; then
  if [ "$GH" = 1 ]; then
    git config user.email "$(gh api user -q .id)+$USUARIO@users.noreply.github.com"
  else
    git config user.email "$USUARIO@users.noreply.github.com"
  fi
  git config user.name "$USUARIO"
fi
git add -A
git diff --cached --quiet || git commit -q -m "perfil"
echo "ok"

passo "2/3  Criando o repositório $REPO"
if [ -n "${REMOTO:-}" ]; then
  echo "usando o endereço de REMOTO: $URL"
elif [ "$GH" = 1 ]; then
  if gh repo view "$REPO" >/dev/null 2>&1; then
    echo "já existe, vou só enviar"
  else
    gh repo create "$REPO" --public >/dev/null
    echo "criado (público)"
  fi
else
  echo "Sem o GitHub CLI logado. Crie o repositório pelo site:"
  echo "  1. Abra https://github.com/new"
  echo "  2. Nome: $USUARIO   (igual ao da conta)"
  echo "  3. Marque Public e NÃO adicione README, .gitignore nem licença"
  read -r -p "Quando terminar, aperte Enter. " _
fi

passo "3/3  Enviando"
git remote remove origin 2>/dev/null || true
git remote add origin "$URL"
# Com o gh, as credenciais saem dele só para este push, sem mexer na
# configuração global do git.
AUTH=()
[ "$GH" = 1 ] && AUTH=(-c credential.helper= -c "credential.helper=!gh auth git-credential")
if [ "$FORCAR" = 1 ]; then
  git ${AUTH[@]+"${AUTH[@]}"} push -q -f -u origin main
elif ! git ${AUTH[@]+"${AUTH[@]}"} push -q -u origin main; then
  erro "O repositório já tem commits que não estão aqui. Para substituir pelo perfil, rode: bash publicar.sh --forcar"
fi
echo "ok"

# Com o gh, acompanha a primeira rodada da Action, que gera os cards.
if [ "$GH" = 1 ]; then
  passo "Gerando os cards (Action)"
  id=""
  for _ in $(seq 1 15); do
    id=$(gh run list -R "$REPO" -w cards.yml -L 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)
    [ -n "$id" ] && break
    sleep 2
  done
  if [ -n "$id" ] && gh run watch "$id" -R "$REPO" --exit-status >/dev/null 2>&1; then
    echo "cards prontos"
  else
    echo "acompanhe em https://github.com/$REPO/actions"
  fi
fi

passo "Pronto: https://github.com/$USUARIO"
if [ -z "${REMOTO:-}" ]; then
  echo "Opcional: para o card de linguagens contar repositórios privados, crie um"
  echo "token (classic, escopos repo e read:user) e salve como secret GRS_TOKEN:"
  echo "  gh secret set GRS_TOKEN -R $REPO"
fi
