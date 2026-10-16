#!/usr/bin/env python3
"""Coleta a página pública de um processo SISLOG/GO e os documentos que ela lista. Só acesso aberto, sem login.

Caminho (mapeado do HAR de 15/10/2026, processo 111606):
  1. GET  /PanelAquisicao/DetalhesLicitacao?idLicitacao=<id>
     página com chat, situação e lista de documentos; cada documento tem um token `d` fixo.
  2a. documento gerado pelo SISLOG (onclick imprimirDocumento):
      POST /PanelAquisicao/GerarPDFDocumentoView?d=<d>&sei=false  corpo JSON {"d": <d>, "sei": false}
      -> HTML com o texto integral (DOD, ETP, TR, Edital, Ata, pareceres, Termo de Homologação...)
  2b. anexo externo (onclick imprimirDocumentoExterno):
      GET  /PanelAquisicao/GerarPDFDocumentoView?d=<d>&sei=false  -> PDF (propostas, mapa de preços, avisos)
O reCAPTCHA do portal protege só a busca (IsValidReCaptcha); este coletor não usa a busca: os ids vêm do
nosso banco (numero_edital do PNCP, "Pregão - Eletrônico nº 111606/2025" -> 111606).

Educação com o portal: uma requisição por vez, pausa entre elas, cache (não baixa de novo o que já existe),
identificação neutra e parada se o portal responder 429/5xx repetidamente.

Uso:
    python3 training/coletar_sislog.py --ids 111606 104744 --saida training/data/sislog
    python3 training/coletar_sislog.py --ids-arquivo training/config/sislog_ids.txt --saida training/data/sislog
    python3 training/coletar_sislog.py --ids 111606 --saida training/data/sislog --so-pagina
Saída por processo: <saida>/<id>/pagina.html, docs/NN_<rótulo>_<token>.html|.pdf, manifesto.json
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://sislog.go.gov.br"
DETALHE = BASE + "/PanelAquisicao/DetalhesLicitacao?idLicitacao={}"
DOC = BASE + "/PanelAquisicao/GerarPDFDocumentoView?d={}&sei={}"
UA = "Mozilla/5.0 (compatible; LicitaGym-coleta-publica/0.1)"
RE_DOC = re.compile(
    r"onclick=\"(imprimirDocumento(?:Externo)?)\(&#x27;([^&]+)&#x27;,\s*(false|true)\)\"[^>]*>\s*([^<]+?)\s*</a>")
VERSAO = "2026-10-15"


class PortalIndisponivel(RuntimeError):
    pass


def slug(s: str, n: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:n] or "doc"


def pedir(url: str, *, metodo: str = "GET", corpo: bytes | None = None, referer: str | None = None,
          tentativas: int = 3, pausa_erro: float = 10.0) -> tuple[bytes, str]:
    cab = {"User-Agent": UA, "Accept": "*/*"}
    if corpo is not None:
        cab["Content-type"] = "application/json"
    if referer:
        cab["Referer"] = referer
    ultimo = None
    for n in range(tentativas):
        try:
            req = urllib.request.Request(url, data=corpo, headers=cab, method=metodo)
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code == 429 or e.code >= 500:
                time.sleep(pausa_erro * (n + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            ultimo = e
            time.sleep(pausa_erro * (n + 1))
    raise PortalIndisponivel(f"{url}: {ultimo}")


def listar_documentos(pagina: str) -> list[dict]:
    docs, vistos = [], set()
    for fn, d, sei, rotulo in RE_DOC.findall(pagina):
        if d in vistos:
            continue
        vistos.add(d)
        docs.append({"rotulo": html.unescape(rotulo).strip(), "token": d, "sei": sei,
                     "tipo": "externo" if fn.endswith("Externo") else "interno"})
    return docs


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def coletar(id_: str, saida: Path, pausa: float, so_pagina: bool, forcar: bool) -> dict:
    pasta = saida / id_
    (pasta / "docs").mkdir(parents=True, exist_ok=True)
    man_arq = pasta / "manifesto.json"
    anterior = json.loads(man_arq.read_text(encoding="utf-8")) if man_arq.exists() else {}
    ja = {d["token"]: d for d in anterior.get("documentos", []) if d.get("arquivo")}

    url = DETALHE.format(id_)
    bruto, ctype = pedir(url)
    pagina = bruto.decode("utf-8", errors="replace")
    if "idLicitacao" not in pagina and "imprimirDocumento" not in pagina:
        raise PortalIndisponivel(f"{id_}: página sem conteúdo de processo ({len(bruto)} bytes)")
    (pasta / "pagina.html").write_bytes(bruto)
    docs = listar_documentos(pagina)
    manifesto = {"id_sislog": id_, "url": url, "versao_coletor": VERSAO,
                 "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "pagina_sha256": sha256(bruto), "n_documentos": len(docs), "documentos": []}

    for i, d in enumerate(docs, 1):
        reg = dict(d)
        antigo = ja.get(d["token"])
        if antigo and not forcar and (pasta / antigo["arquivo"]).exists():
            reg.update({k: antigo[k] for k in ("arquivo", "bytes", "sha256", "content_type") if k in antigo})
            reg["status"] = "cache"
        elif so_pagina:
            reg["status"] = "nao_baixado"
        else:
            time.sleep(pausa)
            u = DOC.format(d["token"], d["sei"])
            try:
                if d["tipo"] == "interno":
                    corpo = json.dumps({"d": d["token"], "sei": d["sei"] == "true"}).encode()
                    conteudo, ct = pedir(u, metodo="POST", corpo=corpo, referer=url)
                else:
                    conteudo, ct = pedir(u, referer=url)
            except urllib.error.HTTPError as e:
                reg["status"] = f"http_{e.code}"
                manifesto["documentos"].append(reg)
                continue
            ext = "pdf" if "pdf" in ct or conteudo[:4] == b"%PDF" else "html"
            nome = f"docs/{i:02d}_{slug(d['rotulo'])}_{slug(d['token'], 8)}.{ext}"
            (pasta / nome).write_bytes(conteudo)
            reg.update({"arquivo": nome, "bytes": len(conteudo), "sha256": sha256(conteudo),
                        "content_type": ct.split(";")[0], "status": "baixado"})
            if ext == "html" and b"data:image/" in conteudo:
                reg["observacao"] = "contém imagem embutida (documento escaneado): texto pode exigir OCR"
        manifesto["documentos"].append(reg)

    man_arq.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifesto


def ler_ids(a) -> list[str]:
    ids = list(a.ids or [])
    if a.ids_arquivo:
        for linha in a.ids_arquivo.read_text(encoding="utf-8").splitlines():
            linha = linha.split("#")[0].strip()
            if linha:
                ids.append(linha.split()[0])
    ok = [i for i in ids if re.fullmatch(r"\d{5,7}", i)]
    for i in set(ids) - set(ok):
        print(f"  ⚠ id ignorado (não é idLicitacao): {i}")
    return list(dict.fromkeys(ok))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Coleta pública de processos SISLOG/GO (sem login)")
    ap.add_argument("--ids", nargs="*", help="idLicitacao (ex.: 111606)")
    ap.add_argument("--ids-arquivo", type=Path, help="um id por linha; '#' inicia comentário")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--pausa", type=float, default=2.5, help="segundos entre requisições (padrão 2,5)")
    ap.add_argument("--so-pagina", action="store_true", help="só a página e a lista de documentos")
    ap.add_argument("--forcar", action="store_true", help="baixa de novo mesmo o que já está no cache")
    a = ap.parse_args(argv)
    ids = ler_ids(a)
    if not ids:
        sys.exit("Nenhum id: use --ids ou --ids-arquivo.")

    falhas = 0
    for n, id_ in enumerate(ids, 1):
        try:
            m = coletar(id_, a.saida, a.pausa, a.so_pagina, a.forcar)
        except PortalIndisponivel as e:
            falhas += 1
            print(f"[{n}/{len(ids)}] {id_}: ✗ {e}")
            if falhas >= 3:
                sys.exit("Portal falhou 3 vezes: parando para não insistir. Tente mais tarde.")
            continue
        st: dict[str, int] = {}
        for d in m["documentos"]:
            st[d["status"]] = st.get(d["status"], 0) + 1
        print(f"[{n}/{len(ids)}] {id_}: {m['n_documentos']} documentos {st} -> {a.saida / id_}")
        if n < len(ids):
            time.sleep(a.pausa)


if __name__ == "__main__":
    main()
