"""Avalia predições contra o gabarito do conjunto de teste (macro-F1, acurácia, matriz de confusão).

  python training/avaliar.py --gabarito training/data/test.jsonl --pred sft=preds_sft.jsonl --pred regras=preds_regras.jsonl

Cada arquivo de predição: uma linha JSON {"id": ..., "saida": "<texto do modelo>"} ou {"id": ..., "categoria": ...}.
O modelo só deve ir para produção se o macro-F1 superar o baseline de regras (escopo.classificar_texto_item do
coletor LicitaGym) — gere preds_regras.jsonl com --baseline-regras apontando para services/coletor-externo.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import ROTULOS, ler_resposta  # noqa: E402


def carregar_gabarito(caminho: str) -> dict[str, str]:
    out = {}
    for l in open(caminho, encoding="utf-8"):
        r = json.loads(l)
        out[r["id"]] = json.loads(r["response"])["categoria"]
    return out


def carregar_pred(caminho: str) -> dict[str, str | None]:
    out = {}
    for l in open(caminho, encoding="utf-8"):
        r = json.loads(l)
        out[r["id"]] = r.get("categoria") if "categoria" in r else ler_resposta(r.get("saida", ""))
    return out


def metricas(gab: dict[str, str], pred: dict[str, str | None]) -> dict:
    tp, fp, fn = collections.Counter(), collections.Counter(), collections.Counter()
    conf = collections.Counter()
    acertos = invalidas = 0
    for i, y in gab.items():
        p = pred.get(i)
        if p is None:
            invalidas += 1
        conf[(y, p or "∅")] += 1
        if p == y:
            acertos += 1
            tp[y] += 1
        else:
            fn[y] += 1
            if p:
                fp[p] += 1
    por_rotulo = {}
    for r in ROTULOS:
        if tp[r] + fn[r] == 0 and fp[r] == 0:
            continue
        prec = tp[r] / (tp[r] + fp[r]) if tp[r] + fp[r] else 0.0
        rec = tp[r] / (tp[r] + fn[r]) if tp[r] + fn[r] else 0.0
        por_rotulo[r] = {"precisao": round(prec, 3), "recall": round(rec, 3),
                         "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0, "suporte": tp[r] + fn[r]}
    presentes = [v["f1"] for k, v in por_rotulo.items() if v["suporte"]]
    return {"n": len(gab), "acuracia": round(acertos / len(gab), 3) if gab else 0.0,
            "macro_f1": round(sum(presentes) / len(presentes), 3) if presentes else 0.0,
            "saidas_invalidas": invalidas, "por_rotulo": por_rotulo,
            "confusao": {f"{a}->{b}": n for (a, b), n in sorted(conf.items()) if a != b}}


def baseline_regras(gabarito: str, coletor_dir: str, saida: str) -> None:
    """Predições do classificador de regras do LicitaGym (escopo.classificar_texto_item) para o mesmo teste."""
    sys.path.insert(0, coletor_dir)
    from coletor.escopo import classificar_texto_item  # type: ignore
    with open(saida, "w", encoding="utf-8") as f:
        for l in open(gabarito, encoding="utf-8"):
            r = json.loads(l)
            item = r["prompt"].rsplit("Item: ", 1)[-1]
            cat, _ = classificar_texto_item(item)
            cat = "fora" if cat in (None, "catmat") else cat
            f.write(json.dumps({"id": r["id"], "categoria": cat if cat in ROTULOS else "fora"}, ensure_ascii=False) + "\n")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gabarito", required=True)
    ap.add_argument("--pred", action="append", default=[], help="nome=arquivo.jsonl (repetível)")
    ap.add_argument("--baseline-regras", metavar="COLETOR_DIR", help="gera preds_regras.jsonl com o classificador do coletor")
    a = ap.parse_args(argv)
    if a.baseline_regras:
        baseline_regras(a.gabarito, a.baseline_regras, "preds_regras.jsonl")
        a.pred.append("regras=preds_regras.jsonl")
    gab = carregar_gabarito(a.gabarito)
    res = {nome: metricas(gab, carregar_pred(arq)) for nome, arq in (p.split("=", 1) for p in a.pred)}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if "sft" in res and "regras" in res:
        ok = res["sft"]["macro_f1"] > res["regras"]["macro_f1"]
        print(f"\nCRITÉRIO DE ACEITE (macro-F1 SFT > regras): {'APROVADO' if ok else 'REPROVADO'}")


if __name__ == "__main__":
    main()
