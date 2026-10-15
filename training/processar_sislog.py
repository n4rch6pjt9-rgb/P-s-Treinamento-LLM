#!/usr/bin/env python3
"""Roda a extração completa nos processos baixados pelo coletar_sislog.py.

Para cada <base>/<id>/:
  1. acha a Ata da sessão pelo CONTEÚDO (HTML com "TROCA DE MENSAGENS"), não pelo nome: o rótulo muda de órgão
     para órgão ("Ata Contratação ...", "Ata FINAL do Pregão ..."); se houver mais de uma, usa a maior (mais completa);
  2. extrair_ata_sislog.py  -> ata.json
  3. rotular_chat.py        -> chat.jsonl (autor pela ata quando houver)
  4. extrair_decisoes_sislog.py -> decisoes.jsonl
e grava um resumo por processo em <base>/_resumo.tsv.

Uso:
    python3 training/processar_sislog.py --base training/data/sislog
    python3 training/processar_sislog.py --base training/data/sislog --ids 116068 104744
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def achar_ata(docs: Path) -> Path | None:
    candidatos = []
    for p in docs.glob("*.html"):
        nome = p.name.lower()
        if re.search(r"arp|minuta|errata|registro_de_pre", nome):
            continue
        with p.open("rb") as f:
            cabeca = f.read(4_000_000)
        if b"TROCA DE MENSAGENS" in cabeca or b"Hist\xc3\xb3rico da Sess\xc3\xa3o P\xc3\xbablica" in cabeca:
            candidatos.append(p)
    return max(candidatos, key=lambda p: p.stat().st_size) if candidatos else None


def rodar(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def contar(jsonl: Path, campo: str) -> dict:
    if not jsonl.exists():
        return {}
    return dict(Counter(json.loads(l).get(campo) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Extração completa dos processos SISLOG baixados")
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--ids", nargs="*")
    a = ap.parse_args(argv)
    pastas = sorted(p for p in a.base.iterdir() if p.is_dir() and (p / "pagina.html").exists()
                    and (not a.ids or p.name in a.ids))
    linhas = ["id\tata\tmensagens\tpendente_llm\tsem_autor\tdecisoes\ttipos_decisao"]
    for p in pastas:
        pid, docs = p.name, p / "docs"
        ata = achar_ata(docs) if docs.exists() else None
        args_chat = [str(AQUI / "rotular_chat.py"), "--html", str(p / "pagina.html"), "--processo", pid,
                     "--saida", str(p / "chat.jsonl")]
        if ata:
            rc, out = rodar([str(AQUI / "extrair_ata_sislog.py"), str(ata), "--saida", str(p / "ata.json")])
            print(f"[{pid}] ata: {ata.name}\n   {out.splitlines()[0] if out else ''}")
            if rc == 0:
                args_chat += ["--ata", str(p / "ata.json")]
        else:
            print(f"[{pid}] sem Ata de sessão nos documentos (dispensa ou ata não publicada)")
        rc, out = rodar(args_chat)
        print("   " + " | ".join(l.strip() for l in out.splitlines()[1:3]))
        rc, out = rodar([str(AQUI / "extrair_decisoes_sislog.py"), "--pasta", str(docs), "--processo", pid,
                         "--saida", str(p / "decisoes.jsonl"), "--chat", str(p / "chat.jsonl")])
        print("   " + " | ".join(l.strip() for l in out.splitlines() if l.startswith(("TR", "✅"))))
        st = contar(p / "chat.jsonl", "status")
        au = contar(p / "chat.jsonl", "autor")
        tipos = contar(p / "decisoes.jsonl", "tipo")
        total = sum(st.values())
        linhas.append(f"{pid}\t{ata.name if ata else '-'}\t{total}\t{st.get('pendente_llm', 0)}\t"
                      f"{au.get('indeterminado', 0)}\t{sum(tipos.values())}\t{json.dumps(tipos, ensure_ascii=False)}")
    (a.base / "_resumo.tsv").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\nResumo -> {a.base / '_resumo.tsv'}")


if __name__ == "__main__":
    main()
