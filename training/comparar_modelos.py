"""Mede modelos de rótulo contra o gabarito revisado à mão (training/data/gabarito.csv).

Para cada modelo pedido, classifica os itens do gabarito com o MESMO prompt e o MESMO parser do rotular_ollama.py
(importa `classificar_lote` de lá), guarda as respostas em cache (data/comparacao/<modelo>.json, para retomar) e
imprime acerto geral, acerto por rótulo (precisão e cobertura), matriz de confusão e tempo por item.

Também mede, sem chamar modelo nenhum, os rótulos que já estão no checkpoint, separados pela origem
(gemini, mistral:latest, regra:...), para comparar com o que os modelos novos fariam.

Uso:
  python3 training/comparar_modelos.py --modelos mistral:latest qwen3-coder:30b gpt-oss:120b-cloud
  python3 training/comparar_modelos.py --so-checkpoint            # só mede o que já está rotulado
  python3 training/comparar_modelos.py --modelos qwen3-coder:30b --lote 5 --mostrar-erros 15
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "data"
sys.path.insert(0, str(PASTA))
ROTULOS = ("forte", "fraco", "piso", "borracha", "obra_piso", "manutencao", "fora")
# Régua de 3 (lead forte / acessório / resto): como o gabarito preenchido com o contexto de produto classifica.
PARA_3 = {"forte": "forte", "piso": "forte", "borracha": "forte", "manutencao": "forte",
          "fraco": "fraco", "obra_piso": "fora", "fora": "fora"}


def ler_gabarito() -> dict[str, str]:
    caminho = DADOS / "gabarito.csv"
    if not caminho.exists():
        sys.exit("Não achei training/data/gabarito.csv. Revise o gabarito_revisar.csv e salve com esse nome.")
    gab, invalidos = {}, []
    for r in csv.DictReader(open(caminho, encoding="utf-8-sig")):
        cat = (r.get("categoria") or "").strip().lower()
        if not cat:
            continue
        if cat not in ROTULOS:
            invalidos.append((r["id"], cat))
            continue
        gab[r["id"].strip()] = cat
    if invalidos:
        print(f"⚠️ {len(invalidos)} linhas com categoria inválida foram ignoradas, ex.: {invalidos[:5]}")
    if not gab:
        sys.exit("O gabarito não tem nenhuma linha com `categoria` preenchida.")
    return gab


REGUA = "7"


def relatorio(nome: str, gab: dict[str, str], pred: dict[str, str], segundos: float | None,
              cand: dict, mostrar_erros: int) -> dict:
    if REGUA == "3":
        gab = {i: PARA_3[r] for i, r in gab.items()}
        pred = {i: PARA_3.get(r, r) for i, r in pred.items()}
    ids = [i for i in gab if i in pred]
    if not ids:
        print(f"\n=== {nome}: nenhum item do gabarito com resposta ===")
        return {}
    acertos = sum(gab[i] == pred[i] for i in ids)
    print(f"\n=== {nome}: {acertos}/{len(ids)} = {acertos / len(ids):.0%} de acerto"
          + (f" | sem resposta: {len(gab) - len(ids)}" if len(ids) < len(gab) else "")
          + (f" | {segundos / len(ids):.1f} s/item" if segundos else "") + " ===")
    print(f"  {'rótulo':11s} {'no gabarito':>11s} {'precisão':>9s} {'cobertura':>9s}")
    for rot in ROTULOS:
        verdadeiros = [i for i in ids if gab[i] == rot]
        previstos = [i for i in ids if pred[i] == rot]
        if not verdadeiros and not previstos:
            continue
        vp = sum(1 for i in previstos if gab[i] == rot)
        prec = f"{vp / len(previstos):.0%}" if previstos else "-"
        cob = f"{vp / len(verdadeiros):.0%}" if verdadeiros else "-"
        print(f"  {rot:11s} {len(verdadeiros):11d} {prec:>9s} {cob:>9s}")
    confusao = Counter((gab[i], pred[i]) for i in ids if gab[i] != pred[i])
    if confusao:
        print("  confusões mais comuns (gabarito -> modelo):",
              ", ".join(f"{g}->{p} ({n})" for (g, p), n in confusao.most_common(6)))
    if mostrar_erros:
        for i in [i for i in ids if gab[i] != pred[i]][:mostrar_erros]:
            print(f"    ✗ {gab[i]:10s} <- {pred[i]:10s} | {cand.get(i, {}).get('descricao', '')[:90]}")
    return {"acerto": acertos / len(ids), "n": len(ids)}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", nargs="*", default=[])
    ap.add_argument("--lote", type=int, default=5)
    ap.add_argument("--ollama-url", default="http://localhost:11434/api/generate")
    ap.add_argument("--so-checkpoint", action="store_true")
    ap.add_argument("--mostrar-erros", type=int, default=10)
    ap.add_argument("--regua", choices=["7", "3"], default="7",
                    help="3 = converte as respostas de 7 rótulos para forte/fraco/fora antes de medir")
    a = ap.parse_args(argv)
    global REGUA
    REGUA = a.regua

    gab = ler_gabarito()
    cand = {}
    with open(DADOS / "candidatos.jsonl", encoding="utf-8") as f:
        for linha in f:
            c = json.loads(linha)
            if c["id"] in gab:
                cand[c["id"]] = c
    print(f"Gabarito: {len(gab)} itens | " + ", ".join(f"{k}={v}" for k, v in Counter(gab.values()).most_common()))

    # 1) O que já está no checkpoint, por origem
    ck = json.load(open(DADOS / "checkpoint_gemini.json", encoding="utf-8"))
    origem_path = DADOS / "checkpoint_origem.json"
    origem = json.load(open(origem_path, encoding="utf-8")) if origem_path.exists() else {}
    por_origem: dict[str, dict[str, str]] = defaultdict(dict)
    for i in gab:
        if i in ck:
            o = origem.get(i, "desconhecida")
            por_origem["regra" if o.startswith("regra") else o][i] = ck[i]
    resumo = {}
    for o, pred in sorted(por_origem.items()):
        resumo[f"checkpoint:{o}"] = relatorio(f"checkpoint ({o})", gab, pred, None, cand, a.mostrar_erros)

    if a.so_checkpoint or not a.modelos:
        return

    # 2) Modelos via Ollama, com o mesmo prompt e parser do rotulador
    try:
        from rotular_ollama import classificar_lote
    except ImportError as e:
        sys.exit(f"Não consegui importar classificar_lote do rotular_ollama.py: {e}")

    pasta_cache = DADOS / "comparacao"
    pasta_cache.mkdir(exist_ok=True)
    itens = [cand[i] for i in gab if i in cand]
    for modelo in a.modelos:
        cache_path = pasta_cache / (re.sub(r"[^\w.-]", "_", modelo) + ".json")
        cache = json.load(open(cache_path, encoding="utf-8")) if cache_path.exists() else {"pred": {}, "segundos": 0.0}
        pend = [c for c in itens if c["id"] not in cache["pred"]]
        print(f"\n🤖 {modelo}: {len(pend)} itens para classificar (cache: {len(cache['pred'])})")
        for k in range(0, len(pend), a.lote):
            lote = pend[k:k + a.lote]
            t0 = time.time()
            try:
                novas = classificar_lote(a.ollama_url, modelo, lote)
            except Exception as e:  # noqa: BLE001 - erro de rede/modelo não derruba a comparação
                print(f"  ⚠️ lote {k // a.lote + 1}: {e}", file=sys.stderr)
                novas = {}
            cache["segundos"] += time.time() - t0
            cache["pred"].update(novas)
            json.dump(cache, open(cache_path, "w", encoding="utf-8"))
            print(f"  {min(k + a.lote, len(pend))}/{len(pend)}", end="\r")
        resumo[modelo] = relatorio(modelo, gab, cache["pred"], cache["segundos"], cand, a.mostrar_erros)

    print("\n=== Resumo ===")
    for nome, r in sorted(resumo.items(), key=lambda x: -(x[1] or {}).get("acerto", 0)):
        if r:
            print(f"  {r['acerto']:.0%}  ({r['n']:3d} itens)  {nome}")


if __name__ == "__main__":
    main()
