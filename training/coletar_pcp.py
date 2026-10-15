#!/usr/bin/env python3
"""Coleta pública do chat do Portal de Compras Públicas (portaldecompraspublicas.com.br). Sem login, sem captcha.

Caminho (mapeado do HAR de 15/10/2026, processo 489437 de Porto Alegre):
    GET https://compras.api.portaldecompraspublicas.com.br/v1/licitacao/<id>/chat?pagina=N
    -> {"codigoUltimaFrase": ..., "frasesChat": [{"apelido", "dataHoraFrase" (UTC), "frase"}, ...]}
    50 frases por página, da mais nova para a mais antiga; página vazia = fim.
O id é o número no fim do linkSistemaOrigem do PNCP (.../PE-00023-2026-2026-507693 -> 507693).
Autor vem explícito no apelido: "Sistema", "Pregoeiro" ou "F. <razão social (cortada em 40 caracteres)>".

Documentos (mapeados do HAR de 15/10/2026, processo 507693, página renderizada no servidor com o estado da API):
    GET  .../v2/licitacao/<id>/documentos/processo     edital, contratos (url direta) e relatórios gerados sob
                                                        demanda (tipoDownLoad 2/4 + "parametros", ex. "Total,<id>")
    GET  .../v2/licitacao/<id>/documentos/fornecedores documentos anexados pelos fornecedores (só a lista, por padrão)
    GET  .../v2/licitacao/<id>/itens?pagina=N           itens: descrição, quantidade, valor de referência, melhor lance
    POST https://conteudo.api.portaldecompraspublicas.com.br/v1/arquivo/download
         {"codigoGeradorArquivo":0,"codigoTipoGerador":<tipoDownLoad>,"codigoUsuarioEntidade":10,
          "parametros":"Total,<id>","reprocessar":false}  -> gera o relatório; repete com o codigoGeradorArquivo
         devolvido até vir {"url"} (o próprio site faz assim, como visitante). Gerar relatório custa processamento
         do portal: por padrão só Ata Final, Vencedores, Termo de Homologação e Pedidos de Esclarecimento.

Uso:
    python3 training/coletar_pcp.py --processos training/config/pcp_processos.tsv --saida training/data/pcp
    python3 training/coletar_pcp.py --processos training/config/pcp_processos.tsv --saida training/data/pcp \
        --so-homologados --limite 3
Saída: <saida>/<id>/chat_bruto.json (páginas como vieram), chat.jsonl (cronológico, normalizado), manifesto.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://compras.api.portaldecompraspublicas.com.br/v1/licitacao/{}/chat?pagina={}"
COMPRAS = "https://compras.api.portaldecompraspublicas.com.br/v2/licitacao/{}"
GERADOR = "https://conteudo.api.portaldecompraspublicas.com.br/v1/arquivo/download"
RELATORIOS_PADRAO = ["Ata Final", "Vencedores", "Termo de Homologação", "Pedidos de Esclarecimento"]
UA = "Mozilla/5.0 (compatible; LicitaGym-coleta-publica/0.1)"
VERSAO = "2026-10-15"
BRT = timezone(timedelta(hours=-3))
RE_LOTE = re.compile(r"\b(lote|item)\s+0*(\d{1,4})\b", re.I)


class PortalIndisponivel(RuntimeError):
    pass


def pedir_json(url: str, tentativas: int = 3, pausa_erro: float = 10.0, corpo: dict | None = None):
    cab = {"User-Agent": UA, "Accept": "application/json", "Origin": "https://www.portaldecompraspublicas.com.br",
           "Referer": "https://www.portaldecompraspublicas.com.br/"}
    dados = None
    if corpo is not None:
        cab["Content-Type"] = "application/json"
        dados = json.dumps(corpo).encode()
    ultimo = None
    for n in range(tentativas):
        try:
            req = urllib.request.Request(url, data=dados, headers=cab, method="POST" if dados else "GET")
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code == 429 or e.code >= 500:
                time.sleep(pausa_erro * (n + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo = e
            time.sleep(pausa_erro * (n + 1))
    raise PortalIndisponivel(f"{url}: {ultimo}")


def ler_processos(caminho: Path) -> list[dict]:
    por_id: dict[str, dict] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        p = (linha.split("\t") + ["", "", ""])[:3]
        if not re.fullmatch(r"\d{5,7}", p[2].strip()):
            print(f"  ⚠ sem id do portal (link do PNCP não aponta para o processo): {p[0]}")
            continue
        reg = por_id.setdefault(p[2].strip(), {"id_pcp": p[2].strip(), "codigos_externos": [], "homologacao": None})
        reg["codigos_externos"].append(p[0])  # o mesmo processo do portal pode ter 2 compras no PNCP
        reg["homologacao"] = reg["homologacao"] or (p[1] or None)
    return list(por_id.values())


def autor(apelido: str) -> tuple[str, str | None]:
    a = (apelido or "").strip()
    if a.lower() == "sistema":
        return "sistema", None
    if a.lower() in ("pregoeiro", "pregoeira", "agente de contratação", "agente de contratacao", "comissão"):
        return "pregoeiro", None
    if a.startswith("F. "):
        return "fornecedor", a[3:].strip()
    return "indeterminado", None


def normalizar(id_pcp: str, frases: list[dict]) -> list[dict]:
    saida = []
    for seq, f in enumerate(reversed(frases), 1):  # API devolve da mais nova para a mais antiga
        utc = datetime.fromisoformat(f["dataHoraFrase"].replace("Z", "+00:00"))
        quem, empresa = autor(f.get("apelido", ""))
        texto = (f.get("frase") or "").strip()
        lotes = sorted({int(n) for _, n in RE_LOTE.findall(texto)})
        saida.append({"id": f"pcp-{id_pcp}-{seq:05d}", "origem": "pcp", "processo": id_pcp, "seq": seq,
                      "data_hora_utc": utc.isoformat(), "data_hora_brasilia": utc.astimezone(BRT).isoformat(),
                      "autor": quem, "autor_por": "portal", "empresa": empresa, "apelido": f.get("apelido"),
                      "lotes": lotes, "texto": texto})
    return saida


def baixar(url: str, destino: Path) -> int:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
        b = r.read()
    destino.write_bytes(b)
    return len(b)


def slug(s: str, n: int = 60) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:n] or "doc"


def gerar_relatorio(doc: dict, pausa: float, espera_max: float = 180.0) -> str | None:
    """Pede o relatório ao gerador do portal e espera a url (o site faz polling igual)."""
    corpo = {"codigoGeradorArquivo": 0, "codigoTipoGerador": doc.get("tipoDownLoad"), "codigoUsuarioEntidade": 10,
             "parametros": doc.get("parametros") or "", "reprocessar": False}
    inicio = time.time()
    while time.time() - inicio < espera_max:
        r = pedir_json(GERADOR, corpo=corpo) or {}
        if r.get("url"):
            return r["url"]
        if r.get("erro") or not r.get("codigoGeradorArquivo"):
            return None
        corpo["codigoGeradorArquivo"] = r["codigoGeradorArquivo"]
        time.sleep(max(pausa, 4.0))
    return None


def coletar_docs(proc: dict, pasta: Path, pausa: float, relatorios: list[str], docs_fornecedores: bool,
                 anterior: dict) -> dict:
    (pasta / "docs").mkdir(exist_ok=True)
    ja = {d.get("chave"): d for d in anterior.get("documentos", []) if d.get("arquivo")}
    base = COMPRAS.format(proc["id_pcp"])
    lista = pedir_json(f"{base}/documentos/processo") or []
    time.sleep(pausa)
    forn = pedir_json(f"{base}/documentos/fornecedores") or []
    (pasta / "documentos_processo.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "documentos_fornecedores.json").write_text(json.dumps(forn, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    itens, pagina = [], 1
    while True:  # itens paginados (12 por página)
        time.sleep(pausa)
        d = pedir_json(f"{base}/itens?pagina={pagina}") or {}
        bloco = (d.get("itens") or {})
        itens += bloco.get("result") or []
        if d.get("lotes"):
            itens += [{"_lote": x} for x in (d["lotes"].get("result") if isinstance(d["lotes"], dict) else d["lotes"]) or []]
        if not bloco.get("nextPage"):
            break
        pagina = bloco["nextPage"]
    (pasta / "itens.json").write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")

    alvos = []
    for i, doc in enumerate(lista, 1):
        nome = doc.get("nome") or doc.get("tituloDocumento") or "doc"
        if doc.get("url"):
            alvos.append((i, doc, nome, "arquivo"))
        elif doc.get("parametros") and nome in relatorios:
            alvos.append((i, doc, nome, "relatorio"))
    if docs_fornecedores:
        for f in forn:
            for doc in f.get("documentos") or []:
                if doc.get("url"):
                    alvos.append((len(alvos) + 100, doc, f"{f.get('razaoSocial', '')} {doc.get('tituloDocumento', '')}",
                                  "fornecedor"))
    registros = []
    for i, doc, nome, origem in alvos:
        chave = doc.get("idArquivo") or doc.get("parametros") or nome
        reg = {"chave": chave, "nome": nome, "tipo": doc.get("tipo") or doc.get("tipoDocumento"), "origem": origem,
               "data": doc.get("dataHora")}
        antigo = ja.get(chave)
        if antigo and (pasta / antigo["arquivo"]).exists():
            reg.update(arquivo=antigo["arquivo"], bytes=antigo.get("bytes"), status="cache")
            registros.append(reg)
            continue
        time.sleep(pausa)
        try:
            url = doc["url"] if origem != "relatorio" else gerar_relatorio(doc, pausa)
            if not url:
                reg["status"] = "relatorio_indisponivel"
                registros.append(reg)
                continue
            ext = Path(nome).suffix.lower() if Path(nome).suffix.lower() in (".pdf", ".zip", ".doc", ".docx",
                                                                              ".xls", ".xlsx", ".odt") else ".pdf"
            arq = f"docs/{i:03d}_{origem}_{slug(Path(nome).stem)}{ext}"
            reg.update(arquivo=arq, bytes=baixar(url, pasta / arq), url=url, status="baixado")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, PortalIndisponivel) as e:
            reg["status"] = f"erro: {e}"[:120]
        registros.append(reg)
    return {"documentos": registros, "itens": len(itens), "documentos_listados": len(lista),
            "fornecedores_com_docs": sum(1 for f in forn if f.get("documentos"))}


def coletar(proc: dict, saida: Path, pausa: float, max_paginas: int, forcar: bool,
            relatorios: list[str] | None = None, com_docs: bool = True, docs_fornecedores: bool = False) -> dict:
    pasta = saida / proc["id_pcp"]
    pasta.mkdir(parents=True, exist_ok=True)
    man_arq = pasta / "manifesto.json"
    anterior = json.loads(man_arq.read_text(encoding="utf-8")) if man_arq.exists() else {}
    if anterior and not forcar and anterior.get("completo") and proc["homologacao"] \
            and (anterior.get("documentos") is not None or not com_docs):  # homologado: nada muda mais
        anterior["status"] = "cache"
        return anterior
    frases: list[dict] = []
    ultima = None
    completo = False
    for pagina in range(1, max_paginas + 1):
        d = pedir_json(API.format(proc["id_pcp"], pagina))
        lote = d.get("frasesChat") or []
        if pagina == 1:
            ultima = d.get("codigoUltimaFrase")
        if not lote:
            completo = True
            break
        frases += lote
        time.sleep(pausa)
    (pasta / "chat_bruto.json").write_text(json.dumps({"codigoUltimaFrase": ultima, "frasesChat": frases},
                                                      ensure_ascii=False), encoding="utf-8")
    chat = normalizar(proc["id_pcp"], frases)
    (pasta / "chat.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chat),
                                      encoding="utf-8")
    manifesto = {**proc, "fonte": API.format(proc["id_pcp"], "N"), "versao_coletor": VERSAO,
                 "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "paginas": pagina if completo else max_paginas, "completo": completo,
                 "codigoUltimaFrase": ultima, "mensagens": len(chat),
                 "autores": dict(Counter(c["autor"] for c in chat)), "status": "baixado"}
    if com_docs:
        time.sleep(pausa)
        manifesto.update(coletar_docs(proc, pasta, pausa, relatorios or RELATORIOS_PADRAO, docs_fornecedores,
                                      anterior))
    man_arq.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifesto


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Coleta pública do chat do Portal de Compras Públicas")
    ap.add_argument("--processos", type=Path, required=True, help="TSV codigo_externo/homologacao/id_pcp")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--pausa", type=float, default=2.0, help="segundos entre requisições (padrão 2)")
    ap.add_argument("--max-paginas", type=int, default=400, help="teto de páginas por processo (50 frases cada)")
    ap.add_argument("--so-homologados", action="store_true")
    ap.add_argument("--limite", type=int)
    ap.add_argument("--forcar", action="store_true", help="coleta de novo mesmo homologado já completo")
    ap.add_argument("--so-chat", action="store_true", help="não busca documentos nem itens")
    ap.add_argument("--relatorios", nargs="*", default=RELATORIOS_PADRAO,
                    help="relatórios gerados a baixar (nomes como aparecem no portal)")
    ap.add_argument("--docs-fornecedores", action="store_true",
                    help="baixa também propostas/habilitação anexadas pelos fornecedores (podem ter dados pessoais)")
    a = ap.parse_args(argv)

    procs = ler_processos(a.processos)
    if a.so_homologados:
        procs = [p for p in procs if p["homologacao"]]
    if a.limite:
        procs = procs[: a.limite]
    falhas = 0
    for n, p in enumerate(procs, 1):
        try:
            m = coletar(p, a.saida, a.pausa, a.max_paginas, a.forcar, a.relatorios, not a.so_chat,
                        a.docs_fornecedores)
        except (PortalIndisponivel, urllib.error.HTTPError) as e:
            falhas += 1
            print(f"[{n}/{len(procs)}] {p['id_pcp']}: ✗ {e}")
            if falhas >= 3:
                sys.exit("Portal falhou 3 vezes: parando para não insistir. Tente mais tarde.")
            continue
        aviso = "" if m.get("completo") else " ⚠ parou no teto de páginas"
        docs = ""
        if m.get("documentos") is not None:
            st = Counter(d["status"].split(":")[0] for d in m["documentos"])
            docs = f" | {m.get('itens', 0)} itens | documentos {dict(st)}"
        print(f"[{n}/{len(procs)}] {p['id_pcp']} ({', '.join(p['codigos_externos'])}): {m['mensagens']} mensagens "
              f"{m['autores']}{docs} [{m['status']}]{aviso}")
        if n < len(procs) and m["status"] != "cache":
            time.sleep(a.pausa)


if __name__ == "__main__":
    main()
