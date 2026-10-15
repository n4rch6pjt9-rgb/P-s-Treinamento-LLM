"""Separa os rótulos `fraco` feitos com a definição antiga (material esportivo genérico) pela régua nova.

Régua nova (decisão de 14/10/2026, comum.py): `fraco` = acessório de treino de academia de pequeno porte.
Material de esporte coletivo, de lutas/artes marciais, uniforme, calçado, premiação e brinde = `fora`.

Não altera o checkpoint. Gera:
  - data/revisao_fraco.csv: todos os `fraco` antigos com a sugestão nova (fora | fraco | revisar) e a regra que decidiu;
  - data/reclassificacao_fraco.json: {id: rótulo} só das decisões por regra segura, para aplicar depois da
    conferência por amostra (ver --aplicar).

Uso:
  python3 training/reclassificar_fraco.py                 # gera os dois arquivos e imprime o resumo
  python3 training/reclassificar_fraco.py --amostra 30     # mostra 30 exemplos de cada grupo para conferir
  python3 training/reclassificar_fraco.py --aplicar        # grava as decisões seguras no checkpoint (com backup)
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path

DADOS = Path(__file__).resolve().parent / "data"


def norm(t: str | None) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)


# Ordem importa: a primeira regra que casa decide. Regras de `fraco` vêm antes porque são as mais específicas
# (ex.: "bola suíça" não pode cair em "bola de ...").
REGRAS: list[tuple[str, str, str]] = [
    # Ginástica rítmica é esporte: decide antes de "bola"/"corda" caírem em fraco
    ("fora", "ginastica_ritmica", r"\b(ginastica ritmica|maca(s)? (de |para )?(gr|ginastica)|macas conectaveis|fita (de |para )?(gr|ginastica)|arco (para |de )?(gr|ginastica ritmica)|bola (de )?ginastica ritmica)"),
    # --- continua fraco: acessório de treino de academia
    ("fraco", "elastico_band", r"\b(mini ?band|super ?band|theraband|faixa elastica|elastico (para|de) (treino|exercicio|resistencia)|tubo elastico|extensor elastico)"),
    ("fraco", "bola_exercicio", r"\bbola (suica|de pilates|pilates|de exercicio|medicinal|medicine|de peso|com peso)|\bmedicine ball|\bslam ?ball|\bwall ?ball|\bbola\b.{0,30}\b(pilates|feijao|amendoim)\b|\bfisio ?b[ao]ll?|\bbola fisio\w*|\bbola (de )?fisioterapia"),
    ("fraco", "caneleira_peso", r"\b(caneleira|tornozeleira)s? (de|com) peso|\b(caneleira|tornozeleira)s?\b.{0,40}\b\d+(,\d+)? ?kg\b"),
    ("fraco", "colchonete", r"\bcolchonete"),
    ("fraco", "corda_individual", r"\bcorda de pular\b(?!.{0,20}coletiva)"),
    ("fraco", "step", r"\bstep\b"),
    # --- vira fora: esporte coletivo, raquete, lutas, premiação, vestuário, brinde, acessório de quadra
    ("fora", "bola_esporte", r"\bbolas? (oficial )?(de |para |em )?(futebol|futsal|campo|society|volei|voleibol|basquete|basketball|handebol|handball|tenis|queimada|iniciacao|inicializacao|beach|praia|rugby|futevolei|polo|malabar)"),
    ("fora", "bola_marca", r"\bbola\b.{0,60}\b(termotec|gomos|camara (de )?(butil|airbility)|matrizada|costurada|fifa|fivb|fiba)"),
    ("fora", "rede_quadra", r"\b(par de )?redes?\b.{0,40}\b(gol|futsal|futebol|campo|society|volei|voleibol|peteca|tenis|basquete|badminton|handebol|beach)"),
    ("fora", "equip_quadra", r"\b(poste|protetor de poste|trave|mini ?gols?|cesta de basquete|tabelas? (de |para )?basquete|aros?\b.{0,25}basquete|antenas? (de |para )?(volei|rede)|placar|marcador de pontos|fita (demarcatoria|de marcacao).{0,40}(volei|futevolei|campo|quadra)|mesa de (ping ?pong|tenis|jogos|pebolim)|pebolim|bocha|jogo de malha|bicicross|ginastica artistica|calibrador (para|de) bolas?|cola para handebol|bombas?\b.{0,40}\b(encher|enchimento)\b.{0,15}\bbolas?)"),
    ("fora", "raquete", r"\b(raquete|peteca|frescobol|tenis de mesa|mesa de tenis|badminton|shuttlecock)"),
    ("fora", "lutas", r"\b(taekwondo|tae kwon do|judo|karate|jiu|kimono|dobok|muay|boxe|kickboxing|capoeira|protetor bucal|protetor de (cabeca|torax)|bandagem)"),
    ("fora", "premiacao", r"\b(trofeu|medalha|placa de homenagem)"),
    ("fora", "vestuario", r"\b(uniforme|camisa|camiseta|calcao|short|meiao|meioes|colete|chuteira|agasalho|bermuda|bone|viseira|tenis (de corrida|esportivo|masculino|feminino|infantil)|tenis -)"),
    ("fora", "caneleira_futebol", r"\b(caneleiras?\b.{0,40}\b(futebol|futsal|protecao|plastico|polipropileno)|joelheiras?|cotoveleiras?)"),
    ("fora", "arbitragem_atletismo", r"\b(cartao (para|de) arbitr|arbitragem|apito|dardo|disco de arremesso|peso de arremesso|martelo de arremesso|atletismo|aparador de chute|beach tennis|trofe[ul]|domino|hidroginastica|poliboias?|flutuador|espaguete (de |para )?(piscina|natacao)|bola (de )?borracha\b.{0,40}iniciacao|bola jumbo)"),
    ("fora", "brinde_utensilio", r"\b(squeeze|garrafa|garrafao|mochila|sacochila|bolsa esportiva|apito|cronometro|bomba (de ar|de encher|para encher)|bandeira|xadrez|tabuleiro|dama|bolsa (para|de) (carregar )?bolas?|prancheta tatica|disco de marcador|marcador (plano )?de campo)"),
    ("fora", "diversos_nao_academia", r"(basquete|goleiros?|carrinho|remo\b|embarcacao|piscina|flutuante|tenis (de )?(futsal|handebol|volei|basquete|corrida)|ritimica|octogono|\bluta\b|taquinho|inflador|equipagem|dry ?fit|badmin|socaite|sacos? (para |de )?(guardar )?bolas?|luvas? (de |p/ |para )?goleiro|sapatilha|ballet|bale\b|jazz|raia (para |de )?piscina|carrinho\b.{0,40}\bbolas?|fita\b.{0,25}\bmarcacao\b.{0,30}\b(volei|futevolei|campo|quadra)|alvos?\b.{0,40}\b(arco|archery|tiro)|tiro com arco|archery|bolas? de borracha|biribol|prancheta|fita (para |de )?demarcacao|bambole|abaco|brinquedo|faixa (de )?graduacao|cabo de guerra|slackline|andador|ortopedic|carrinho (para|de) (armazenagem de )?bolas|sinuca|snooker|bilhar|otoscopio|estetoscopio|trena|futvolei|futevolei|beach ?ten|ligaduras|esparadrapo)"),
    ("fora", "outros_esportes", r"\b(skate|patins|patinete|nadadeira|natacao|touca de natacao|oculos de natacao|prancha de (natacao|surf)|malabar|bicicleta)"),
]
REGRAS_COMPILADAS = [(rot, nome, re.compile(p)) for rot, nome, p in REGRAS]


# Ficam para decisão humana, mas agrupados: material de treino funcional/agilidade pode ser academia ou esporte.
RE_AGILIDADE = re.compile(r"\b(cones?|chapeu chines|prato demarcatorio|escada (de|para) (agilidade|coordenacao|exercicio)|barreiras?|obstaculos?|agilidade|funcional)")


# Lista genérica de material esportivo (vários itens num texto só): nenhuma regra é segura
RE_LISTA_GENERICA = re.compile(r"^(item \d+ - )?(registro de precos|aquisicao|contratacao|fornecimento)\b.{0,60}\bmateria(l|is) esportiv")


# Equipamento de academia (forte pela régua do comum.py) que tinha sido marcado como fraco
RE_FORTE = re.compile(r"\b(kettlebell|halteres?|dumbbells?|anilhas?|barra olimpica|cadeira (abdutora|adutora|extensora|flexora)|leg ?press|esteira (ergometrica|eletrica|profissional)|bicicleta ergometrica|eliptico|transport\b|estacao de musculacao|(estacao|aparelho|maquina) (de )?cross ?over|banco (supino|scott|regulavel|de supino)|smith|power ?rack|gaiola de agachamento|rack (de |para )?(agachamento|halteres|anilhas)|aparelho (de |para )?musculacao)")
# Kits em que a regra de fraco não é segura (cones, escada e barreira junto com elástico ou corda)
NAO_SEGURO_COM_AGILIDADE = {"elastico_band", "corda_individual", "step"}


def decidir(descricao: str) -> tuple[str, str]:
    d = norm(descricao)
    if RE_LISTA_GENERICA.search(d):
        return "revisar", "lista_generica"
    acertos = [(rot, nome) for rot, nome, padrao in REGRAS_COMPILADAS if padrao.search(d)]
    if RE_FORTE.search(d):
        # forte só é seguro se nenhuma regra de fora/fraco também casar (ex.: bola de basquete "crossover")
        return ("forte", "equipamento_academia") if not acertos else ("revisar", "conflito_forte")
    rotulos = {rot for rot, _ in acertos}
    if len(rotulos) > 1:
        return "revisar", "conflito_" + "_".join(sorted(nome for _, nome in acertos))[:60]
    if acertos:
        rot, nome = acertos[0]
        if rot == "fraco" and nome in NAO_SEGURO_COM_AGILIDADE and RE_AGILIDADE.search(d):
            return "revisar", "agilidade_funcional"
        return rot, nome
    if RE_AGILIDADE.search(d):
        return "revisar", "agilidade_funcional"
    return "revisar", ""


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--amostra", type=int, default=0, help="mostra N exemplos por grupo para conferência")
    ap.add_argument("--aplicar", action="store_true", help="grava as decisões seguras no checkpoint (faz backup)")
    a = ap.parse_args(argv)

    caminho_ck = DADOS / "checkpoint_gemini.json"
    ck = json.load(open(caminho_ck, encoding="utf-8"))
    origem_path = DADOS / "checkpoint_origem.json"
    origem = json.load(open(origem_path, encoding="utf-8")) if origem_path.exists() else {}
    cand = {}
    with open(DADOS / "candidatos.jsonl", encoding="utf-8") as f:
        for linha in f:
            c = json.loads(linha)
            cand[c["id"]] = c

    linhas, seguras, cont = [], {}, Counter()
    sem_candidato = 0
    for cid, rot in ck.items():
        if rot != "fraco":
            continue
        c = cand.get(cid)
        if c is None:
            sem_candidato += 1
            continue
        novo, regra = decidir(c.get("descricao", ""))
        cont[(novo, regra)] += 1
        if novo != "revisar":
            seguras[cid] = novo
        linhas.append({"id": cid, "descricao": c.get("descricao", ""), "objeto": c.get("objeto") or "",
                       "rotulo_antigo": "fraco", "sugestao_nova": novo, "regra": regra,
                       "modelo_origem": origem.get(cid, ""), "categoria": "" if novo == "revisar" else novo,
                       "revisado_por": "", "obs": ""})

    linhas.sort(key=lambda l: (l["sugestao_nova"] != "revisar", l["sugestao_nova"], l["regra"]))
    with open(DADOS / "revisao_fraco.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]) if linhas else ["id"])
        w.writeheader()
        w.writerows(linhas)
    json.dump(seguras, open(DADOS / "reclassificacao_fraco.json", "w", encoding="utf-8"), ensure_ascii=False)

    total = len(linhas)
    por_rotulo = Counter(l["sugestao_nova"] for l in linhas)
    print(f"fraco antigos: {total} (sem candidato correspondente: {sem_candidato})")
    for k in ("fora", "fraco", "forte", "revisar"):
        print(f"  {k:8s} {por_rotulo[k]:6d}  ({por_rotulo[k] / max(total, 1):.0%})")
    print("por regra:")
    for (novo, regra), n in sorted(cont.items(), key=lambda x: -x[1]):
        print(f"  {n:6d}  {novo:8s} {regra or '-'}")
    print(f"-> {DADOS / 'revisao_fraco.csv'}\n-> {DADOS / 'reclassificacao_fraco.json'} ({len(seguras)} decisões seguras)")

    if a.amostra:
        rnd = random.Random(7)
        for grupo in ("fora", "fraco", "forte", "revisar"):
            g = [l for l in linhas if l["sugestao_nova"] == grupo]
            print(f"\n=== amostra {grupo} ({len(g)}) ===")
            for l in rnd.sample(g, min(a.amostra, len(g))):
                print(f"  [{l['regra'] or '-':18s}] {norm(l['descricao'])[:110]}")

    if a.aplicar:
        backup = DADOS / "checkpoint_gemini.antes_reclassificacao.json"
        shutil.copyfile(caminho_ck, backup)
        ck.update(seguras)
        json.dump(ck, open(caminho_ck, "w", encoding="utf-8"))
        origem.update({k: f"regra:{decidir(cand[k]['descricao'])[1]}" for k in seguras})
        json.dump(origem, open(origem_path, "w", encoding="utf-8"))
        print(f"\n✅ {len(seguras)} rótulos atualizados no checkpoint (backup em {backup.name}).")


if __name__ == "__main__":
    main()
