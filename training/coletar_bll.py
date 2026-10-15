#!/usr/bin/env python3
"""Coleta pública de processos da BLL Compras (bllcompras.com). Só acesso aberto, sem login e SEM captcha.

Caminho (mapeado dos HARs de 08/10/2026):
  1. GET  /Process/ProcessView?param1=<link do PNCP>   página do processo; nela está o id interno ([gkz]...)
     usado pelas chamadas abaixo (botões doAction(...,'ProcessFiles', ['<id>'])).
  2. GET  /Process/<Endpoint>?param1=<id>  (XHR, devolve JSON {"html": ...}), sem token:
       ProcessReport      relatórios: Ata de Sessão, Vencedores, Adjudicação, Homologação, Lances, Propostas
       ProcessFiles       edital, TR, anexos
       ProcessDocuments   documentos de habilitação exigidos
       ProcessImpeachment impugnações          ProcessClarify  esclarecimentos
       ProcessAlert       notificações do processo
  3. Os PDFs ficam no armazenamento público lanceeletronico.blob.core.windows.net (link direto).
NÃO usamos (exigem reCAPTCHA, token=0cAF...): busca GetProcessByParams, ProcessBatches, GetProcessMessageView,
batchSession; nem BidHistory/GetBatchMessageView (dependem do id de lote que só vem de ProcessBatches).
A Ata de Sessão em PDF já traz movimentos, mensagens e lances.

Entrada: TSV "codigo_externo<TAB>homologacao<TAB>numero_edital<TAB>link" (training/config/bll_processos.tsv),
gerado do banco (linkSistemaOrigem do PNCP).

Uso:
    python3 training/coletar_bll.py --processos training/config/bll_processos.tsv --saida training/data/bll
    python3 training/coletar_bll.py --processos training/config/bll_processos.tsv --saida training/data/bll \
        --so-homologados --limite 5
Saída: <saida>/<codigo_externo com / -> _>/pagina.html, <endpoint>.json, docs/*.pdf, manifesto.json
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
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://bllcompras.com"
BLOB = "https://lanceeletronico.blob.core.windows.net/"
UA = "Mozilla/5.0 (compatible; LicitaGym-coleta-publica/0.1)"
VERSAO = "2026-10-15"
ENDPOINTS = ["ProcessReport", "ProcessFiles", "ProcessDocuments", "ProcessImpeachment", "ProcessClarify",
             "ProcessAlert"]
RE_ID = re.compile(r"doAction\(false,'GET','Process','Process(?:Files|Report|Documents)', \['([^']+)'")
RE_BLOB = re.compile(r'https://lanceeletronico\.blob\.core\.windows\.net/[^"\'\s\\<>]+')


class PortalIndisponivel(RuntimeError):
    pass


def slug(s: str, n: int = 70) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:n] or "doc"


def pedir(url: str, *, referer: str | None = None, xhr: bool = False, tentativas: int = 3,
          pausa_erro: float = 10.0) -> tuple[bytes, str]:
    cab = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        cab["Referer"] = referer
    if xhr:
        cab["X-Requested-With"] = "XMLHttpRequest"
    ultimo = None
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=120) as r:
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
    raise PortalIndisponivel(f"{url[:90]}: {ultimo}")


def url_view(link: str) -> str:
    """O param1 do PNCP vem sem codificação ([gkz]...+/=); o navegador codifica antes de enviar."""
    base, _, p = link.partition("param1=")
    return f"{base}param1={urllib.parse.quote(urllib.parse.unquote(p), safe='')}"


def arquivos_do_html(h: str) -> list[dict]:
    """Linhas de tabela com link para o blob: rótulo (texto da linha) + url."""
    saida, vistos = [], set()
    h = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", h)
    for tr in re.split(r"(?i)<tr\b", h):
        for u in RE_BLOB.findall(tr):
            u = html.unescape(u)
            if u in vistos:
                continue
            vistos.add(u)
            texto = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", "<tr" + tr))).strip()
            saida.append({"url": u, "rotulo": texto[:160] or Path(urllib.parse.urlparse(u).path).name})
    return saida


def ler_processos(caminho: Path) -> list[dict]:
    lista = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        partes = linha.split("\t")
        if len(partes) < 4 or "bllcompras.com/Process/ProcessView" not in partes[3]:
            print(f"  ⚠ linha ignorada: {linha[:80]}")
            continue
        lista.append({"codigo_externo": partes[0], "homologacao": partes[1] or None,
                      "numero_edital": partes[2] or None, "link": partes[3].strip()})
    return lista


def coletar(proc: dict, saida: Path, pausa: float, baixar_pdfs: bool, forcar: bool) -> dict:
    pasta = saida / slug(proc["codigo_externo"].replace("/", "_"), 60)
    (pasta / "docs").mkdir(parents=True, exist_ok=True)
    man_arq = pasta / "manifesto.json"
    anterior = json.loads(man_arq.read_text(encoding="utf-8")) if man_arq.exists() else {}
    ja = {d["url"]: d for d in anterior.get("arquivos", []) if d.get("arquivo")}

    view = url_view(proc["link"])
    bruto, _ = pedir(view)
    (pasta / "pagina.html").write_bytes(bruto)
    pagina = bruto.decode("utf-8", errors="replace")
    m = RE_ID.search(pagina)
    if not m:
        raise PortalIndisponivel(f"{proc['codigo_externo']}: página sem id interno (processo removido ou link inválido?)")
    pid = m.group(1)

    manifesto = {**proc, "url_view": view, "versao_coletor": VERSAO,
                 "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "endpoints": {}, "arquivos": []}
    arquivos: list[dict] = []
    for ep in ENDPOINTS:
        time.sleep(pausa)
        url = f"{BASE}/Process/{ep}?param1={urllib.parse.quote(pid, safe='[]')}"
        try:
            b, ct = pedir(url, referer=view, xhr=True)
        except urllib.error.HTTPError as e:
            manifesto["endpoints"][ep] = f"http_{e.code}"
            continue
        (pasta / f"{ep}.json").write_bytes(b)
        try:
            h = json.loads(b).get("html", "")
        except (json.JSONDecodeError, AttributeError):
            h = b.decode("utf-8", errors="replace")
        achados = arquivos_do_html(h)
        for a in achados:
            a["origem"] = ep
        arquivos += achados
        manifesto["endpoints"][ep] = {"bytes": len(b), "arquivos": len(achados)}

    for i, a in enumerate(arquivos, 1):
        antigo = ja.get(a["url"])
        if antigo and not forcar and (pasta / antigo["arquivo"]).exists():
            a.update({k: antigo[k] for k in ("arquivo", "bytes", "sha256") if k in antigo}, status="cache")
        elif not baixar_pdfs:
            a["status"] = "nao_baixado"
        else:
            time.sleep(pausa)
            try:
                b, ct = pedir(a["url"])
            except urllib.error.HTTPError as e:
                a["status"] = f"http_{e.code}"
                continue
            nome_blob = Path(urllib.parse.urlparse(a["url"]).path).name
            prefixo = slug(a["rotulo"], 50) if a["origem"] != "ProcessReport" else slug(nome_blob.split("_")[0], 30)
            nome = f"docs/{i:02d}_{a['origem'].replace('Process', '')}_{prefixo}_{nome_blob[-12:]}"
            (pasta / nome).write_bytes(b)
            a.update(arquivo=nome, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), status="baixado")
    manifesto["arquivos"] = arquivos
    man_arq.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifesto


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Coleta pública BLL Compras (sem login, sem captcha)")
    ap.add_argument("--processos", type=Path, required=True, help="TSV codigo_externo/homologacao/edital/link")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--pausa", type=float, default=3.0, help="segundos entre requisições (padrão 3)")
    ap.add_argument("--so-homologados", action="store_true")
    ap.add_argument("--limite", type=int, help="no máximo N processos (teste)")
    ap.add_argument("--sem-pdfs", action="store_true", help="só página e listas, sem baixar os PDFs")
    ap.add_argument("--forcar", action="store_true", help="baixa de novo o que já está no cache")
    a = ap.parse_args(argv)

    procs = ler_processos(a.processos)
    if a.so_homologados:
        procs = [p for p in procs if p["homologacao"]]
    if a.limite:
        procs = procs[: a.limite]
    falhas = 0
    for n, p in enumerate(procs, 1):
        try:
            m = coletar(p, a.saida, a.pausa, not a.sem_pdfs, a.forcar)
        except PortalIndisponivel as e:
            falhas += 1
            print(f"[{n}/{len(procs)}] {p['codigo_externo']}: ✗ {e}")
            if falhas >= 3:
                sys.exit("Portal falhou 3 vezes: parando para não insistir. Tente mais tarde.")
            continue
        st: dict[str, int] = {}
        for d in m["arquivos"]:
            st[d["status"]] = st.get(d["status"], 0) + 1
        rel = sum(1 for d in m["arquivos"] if d["origem"] == "ProcessReport")
        print(f"[{n}/{len(procs)}] {p['codigo_externo']} ({p['numero_edital'] or 's/ nº'}): "
              f"{len(m['arquivos'])} arquivos ({rel} relatórios) {st}")
        if n < len(procs):
            time.sleep(a.pausa)


if __name__ == "__main__":
    main()
