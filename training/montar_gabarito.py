"""Sorteia um gabarito pequeno para revisão humana e medição dos modelos de rótulo.

O gabarito é a régua para comparar modelos (Mistral, Qwen, gpt-oss, Gemini): sem ele não dá para saber qual acerta mais.

Amostragem estratificada e determinística (semente fixa):
  - N itens por rótulo atual do checkpoint (forte, fraco, piso, borracha, obra_piso, manutencao, fora);
  - dentro de cada rótulo, metade de cada origem quando houver (gemini x modelo local), para medir os dois;
  - mais M itens "difíceis" da revisão do fraco (agilidade, lista genérica, conflitos, sem regra), se o CSV existir.

Gera dois arquivos em training/data/:
  - gabarito_revisar.csv: id, descricao, objeto e a coluna `categoria` VAZIA para você preencher.
    O rótulo atual NÃO aparece, para não influenciar a revisão.
  - gabarito_chave.json: rótulo e origem de cada item sorteado (usado depois pelo comparar_modelos.py).

Uso:
  python3 training/montar_gabarito.py                  # 20 por rótulo + 20 difíceis (~160 itens)
  python3 training/montar_gabarito.py --por-rotulo 15 --dificeis 10

Depois de revisar, salve como training/data/gabarito.csv (mesmas colunas, `categoria` preenchida com um dos rótulos:
forte, fraco, piso, borracha, obra_piso, manutencao, fora). Linha com `categoria` vazia é ignorada na medição.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

DADOS = Path(__file__).resolve().parent / "data"
ROTULOS = ("forte", "fraco", "piso", "borracha", "obra_piso", "manutencao", "fora")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-rotulo", type=int, default=20)
    ap.add_argument("--dificeis", type=int, default=20)
    ap.add_argument("--semente", type=int, default=2026)
    a = ap.parse_args(argv)
    rnd = random.Random(a.semente)

    ck = json.load(open(DADOS / "checkpoint_gemini.json", encoding="utf-8"))
    origem_path = DADOS / "checkpoint_origem.json"
    origem = json.load(open(origem_path, encoding="utf-8")) if origem_path.exists() else {}
    cand = {}
    with open(DADOS / "candidatos.jsonl", encoding="utf-8") as f:
        for linha in f:
            c = json.loads(linha)
            cand[c["id"]] = c

    def fonte(i: str) -> str:
        o = origem.get(i, "")
        return "gemini" if o == "gemini" else ("regra" if o.startswith("regra") else (o or "desconhecida"))

    # rótulo -> origem -> ids (ordenados para o sorteio ser reprodutível)
    grupos: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for i, rot in sorted(ck.items()):
        if i in cand and rot in ROTULOS:
            grupos[rot][fonte(i)].append(i)

    escolhidos: dict[str, str] = {}  # id -> motivo do sorteio
    for rot in ROTULOS:
        por_origem = grupos.get(rot, {})
        if not por_origem:
            continue
        fontes = sorted(por_origem)
        cota = max(1, a.por_rotulo // len(fontes))
        for fo in fontes:
            ids = por_origem[fo]
            for i in rnd.sample(ids, min(cota, len(ids))):
                escolhidos[i] = f"rotulo:{rot}|origem:{fo}"

    revisao = DADOS / "revisao_fraco.csv"
    if a.dificeis and revisao.exists():
        linhas = [r for r in csv.DictReader(open(revisao, encoding="utf-8"))
                  if r.get("sugestao_nova") == "revisar" and r["id"] in cand and r["id"] not in escolhidos]
        por_regra: dict[str, list[str]] = defaultdict(list)
        for r in sorted(linhas, key=lambda r: r["id"]):
            chave = r.get("regra") or "sem_regra"
            por_regra["conflito" if chave.startswith("conflito") else chave].append(r["id"])
        regras = sorted(por_regra)
        cota = max(1, a.dificeis // max(1, len(regras)))
        for chave in regras:
            for i in rnd.sample(por_regra[chave], min(cota, len(por_regra[chave]))):
                escolhidos[i] = f"dificil:{chave}"

    ids = list(escolhidos)
    rnd.shuffle(ids)  # mistura a ordem para a planilha não vir agrupada por rótulo
    with open(DADOS / "gabarito_revisar.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "descricao", "objeto", "categoria", "obs"])
        w.writeheader()
        for i in ids:
            c = cand[i]
            w.writerow({"id": i, "descricao": c.get("descricao", ""), "objeto": c.get("objeto") or "",
                        "categoria": "", "obs": ""})
    chave = {i: {"rotulo_atual": ck.get(i), "origem": origem.get(i, ""), "sorteio": escolhidos[i]} for i in ids}
    json.dump(chave, open(DADOS / "gabarito_chave.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"✅ {len(ids)} itens -> {DADOS / 'gabarito_revisar.csv'}")
    print("   por sorteio:", dict(Counter(m.split("|")[0] for m in escolhidos.values())))
    print("   por origem :", dict(Counter(fonte(i) for i in ids)))
    print("Preencha a coluna `categoria` e salve como training/data/gabarito.csv.")


if __name__ == "__main__":
    main()
