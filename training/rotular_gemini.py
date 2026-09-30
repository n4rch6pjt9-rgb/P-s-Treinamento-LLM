"""Pré-rótulo com Gemini para REVISÃO HUMANA (não é gabarito).

Lê data/candidatos.jsonl, pede ao Gemini a categoria de cada item em lotes e grava data/rotulos_sugeridos.csv:
  id, origem, descricao, objeto, rotulo_regra, sugestao_gemini, categoria, revisado_por, obs
`categoria` vem preenchida com a sugestão; `revisado_por` vem vazia. Revise (planilha), preencha revisado_por e
salve como data/rotulos.csv. Só linhas revisadas entram no treino (export_dataset.py montar).

Onde regra e Gemini discordam, a linha sobe para o topo (revise primeiro).

  pip install google-genai
  export GEMINI_API_KEY=...
  python training/rotular_gemini.py --limite 500
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import DESCRICAO_ROTULOS, ROTULOS  # noqa: E402

DADOS = Path(__file__).resolve().parent / "data"
EXEMPLOS = [  # few-shot curto; ajuste com casos reais revisados
    ("LEG PRESS 45 GRAUS COM CARGA DE 200 KG", None, "forte"),
    ("Bola de futsal oficial", None, "fraco"),
    ("Placa emborrachada 1x1 m 20 mm para academia", None, "piso"),
    ("Borracha granulada SBR para reposição do campo sintético", None, "borracha"),
    ("Execução de piso emborrachado monolítico no playground", None, "obra_piso"),
    ("Cabo de aço revestido para aparelho de musculação", "Manutenção de equipamentos da academia", "manutencao"),
    ("Caneta esferográfica azul", None, "fora"),
]


def instrucao_lote() -> str:
    regras = "\n".join(f"- {k}: {v}" for k, v in DESCRICAO_ROTULOS.items())
    exemplos = "\n".join(json.dumps({"item": d, "objeto": o, "categoria": c}, ensure_ascii=False) for d, o, c in EXEMPLOS)
    return ("Classifique cada item de licitação pública para a Playfit (equipamentos de academia, pisos de borracha, "
            f"grama sintética). Rótulos:\n{regras}\nExemplos:\n{exemplos}\n"
            "Responda só com uma lista JSON [{\"id\": ..., \"categoria\": ...}] na mesma ordem.")


def classificar_lote(cliente, modelo: str, lote: list[dict]) -> dict[str, str]:
    from google.genai import types
    itens = [{"id": c["id"], "item": c["descricao"][:500], "objeto": (c.get("objeto") or "")[:300]} for c in lote]
    resp = cliente.models.generate_content(
        model=modelo,
        contents=instrucao_lote() + "\nItens:\n" + json.dumps(itens, ensure_ascii=False),
        config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
    )
    out = {}
    for r in json.loads(resp.text or "[]"):
        if isinstance(r, dict) and r.get("categoria") in ROTULOS:
            out[str(r.get("id"))] = r["categoria"]
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="gemini-2.5-flash")
    ap.add_argument("--lote", type=int, default=25)
    ap.add_argument("--limite", type=int, default=0, help="0 = todos os candidatos ainda sem rótulo")
    a = ap.parse_args(argv)

    from google import genai
    cliente = genai.Client()  # lê GEMINI_API_KEY do ambiente

    cand = [json.loads(l) for l in open(DADOS / "candidatos.jsonl", encoding="utf-8")]
    ja = set()
    if (DADOS / "rotulos.csv").exists():
        ja = {r["id"] for r in csv.DictReader(open(DADOS / "rotulos.csv", encoding="utf-8")) if r.get("revisado_por")}
    pend = [c for c in cand if c["id"] not in ja]
    if a.limite:
        pend = pend[: a.limite]

    sugestao: dict[str, str] = {}
    for i in range(0, len(pend), a.lote):
        lote = pend[i : i + a.lote]
        try:
            sugestao.update(classificar_lote(cliente, a.modelo, lote))
        except Exception as e:  # noqa: BLE001
            print(f"lote {i // a.lote}: {e}", file=sys.stderr)
            time.sleep(10)
        print(f"{min(i + a.lote, len(pend))}/{len(pend)}", end="\r")

    linhas = []
    for c in pend:
        s = sugestao.get(c["id"], "")
        linhas.append({"id": c["id"], "origem": c.get("origem"), "descricao": c["descricao"], "objeto": c.get("objeto") or "",
                       "rotulo_regra": c.get("rotulo_regra") or "", "sugestao_gemini": s, "categoria": s,
                       "revisado_por": "", "obs": ""})
    # discordância regra x Gemini primeiro
    linhas.sort(key=lambda l: (not (l["rotulo_regra"] and l["sugestao_gemini"] and l["rotulo_regra"] != l["sugestao_gemini"]),
                               l["sugestao_gemini"] == ""))
    with open(DADOS / "rotulos_sugeridos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]) if linhas else ["id"])
        w.writeheader()
        w.writerows(linhas)
    print(f"\nrotulos_sugeridos.csv: {len(linhas)} linhas ({len(sugestao)} com sugestão)")


if __name__ == "__main__":
    main()
