#!/usr/bin/env python3
"""Lê a ATA DE SESSÃO da BLL Compras (AtaSessaoFinal_*.pdf, baixada pelo coletar_bll.py).

Formato (pdftotext -layout):
    cabeçalho repetido em toda página (município, UF, ATA DE SESSÃO, PREGÃO ELETRÔNICO Nº, Processo, Tipo,
    PREGOEIRO, Data de Publicação);
    MOVIMENTOS DO PROCESSO  -> eventos do processo (propostas, esclarecimentos, mensagens antes dos lotes);
    LOTE n - SITUAÇÃO       -> eventos do lote;
    cada evento: "dd/mm/aaaa hh:mm:ss TIPO [ATOR] [valor]" + linhas de texto até o próximo evento.
Tipos vistos: LANCE <empresa (PARTICIPANTE n)> <valor>, MENSAGEM PREGOEIRO | MENSAGEM <empresa (PARTICIPANTE n)>,
NOTIFICAÇÃO SISTEMA, RECURSO MANIFESTADO <empresa>, DESCLASSIFICAÇÃO DE PARTICIPANTE PREGOEIRO,
ESCLARECIMENTO REQUERIDO <empresa (CNPJ)>, RESPOSTA DE ESCLARECIMENTO PREGOEIRO, CADASTRO/ALTERAÇÃO DE PROPOSTA
<empresa>, e mudanças de fase (PUBLICADO, DISPUTA, JULGAMENTO, HABILITAÇÃO, ADJUDICADO, PRORROGAÇÃO AUTOMÁTICA...).

Saídas:
    --saida   JSON {meta, lotes:[{lote, situacao, fases, lances, eventos}], eventos_processo}
    --chat    JSONL de mensagens/notificações/recursos/desclassificações/esclarecimentos (uma por linha), com autor
              tirado da própria ata (pregoeiro | fornecedor | sistema) e o lote em que aconteceu.
Uso:
    python3 training/extrair_ata_bll.py <AtaSessaoFinal.pdf> --saida ata.json --chat chat.jsonl --processo <id>
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

RE_EVENTO = re.compile(r"^\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\s+(.*?)\s*$")
RE_LOTE = re.compile(r"^\s*(LOTE|ITEM) (\d+) - (.+?)\s*$")
RE_VALOR_FIM = re.compile(r"\s+(-?[\d.]*\d,\d{2,4})\s*$")
RE_SO_VALOR = re.compile(r"^-?[\d.]*\d,\d{2,4}$")
RE_FIM_ATOR = re.compile(r"\((?:PARTICIPANTE \d+|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\)")
ESPERA_ATOR = {"LANCE", "MENSAGEM", "RECURSO MANIFESTADO", "ESCLARECIMENTO REQUERIDO", "IMPUGNAÇÃO"}
RE_PART = re.compile(r"\(PARTICIPANTE (\d+)\)")
RE_CNPJ = re.compile(r"\((\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\)")
TIPOS_COM_ATOR = ["LANCE", "MENSAGEM", "NOTIFICAÇÃO", "RECURSO MANIFESTADO", "DESCLASSIFICAÇÃO DE PARTICIPANTE",
                  "ESCLARECIMENTO REQUERIDO", "RESPOSTA DE ESCLARECIMENTO", "CADASTRO DE PROPOSTA",
                  "ALTERAÇÃO DE PROPOSTA", "RESPOSTA DE RECURSO", "IMPUGNAÇÃO",
                  "RESPOSTA DE IMPUGNAÇÃO", "INABILITAÇÃO DE PARTICIPANTE", "HABILITAÇÃO DE PARTICIPANTE",
                  "CONVOCAÇÃO", "NEGOCIAÇÃO"]
CHAT = {"MENSAGEM", "NOTIFICAÇÃO", "RECURSO MANIFESTADO", "DESCLASSIFICAÇÃO DE PARTICIPANTE",
        "ESCLARECIMENTO REQUERIDO", "RESPOSTA DE ESCLARECIMENTO", "RESPOSTA DE RECURSO",
        "IMPUGNAÇÃO", "RESPOSTA DE IMPUGNAÇÃO", "INABILITAÇÃO DE PARTICIPANTE", "HABILITAÇÃO DE PARTICIPANTE",
        "CONVOCAÇÃO", "NEGOCIAÇÃO"}


def iso(dh: str) -> str:
    return datetime.strptime(dh, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S-03:00")


def valor(s: str | None) -> float | None:
    return float(s.replace(".", "").replace(",", ".")) if s else None


def _pdftotext(pdf: Path, modo: str) -> str:
    return subprocess.run(["pdftotext", modo, "-enc", "UTF-8", str(pdf), "-"],
                          check=True, capture_output=True, text=True).stdout


RODAPE = re.compile(r"^\s*(\d+ de \d+|Gerado em: \d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\s*$")
RODAPE_LAYOUT = re.compile(r"^\s*Gerado em: .*\d+ de \d+\s*$")
FECHA_TEXTO = re.compile(r"^(Razão Social\s+Num|CLASSIFICAÇÃO$|DESCLASSIFICADOS$|INABILITADOS$|MOVIMENTOS DO LOTE$|"
                         r"VALORES UNITÁRIOS FINAIS$|Item: \d+\s+Unidade:)")


def ler_linhas(pdf: Path) -> tuple[list[str], list[str], list[str]]:
    """Conteúdo dos eventos vem do -raw (no -layout a coluna do nome da empresa se mistura com o texto da
    mensagem); a estrutura (a que lote pertence cada evento, itens, classificação) vem do -layout, que mantém a
    ordem da página (no -raw o cabeçalho "LOTE n" às vezes sai depois dos primeiros eventos do lote)."""
    if pdf.suffix.lower() == ".txt":
        raw = lay = pdf.read_text(encoding="utf-8", errors="replace")
    else:
        raw, lay = _pdftotext(pdf, "-raw"), _pdftotext(pdf, "-layout")
    nao_vazias = [l.strip() for l in lay.replace("\f", "\n").split("\n") if l.strip()]
    fim = nao_vazias.index("MOVIMENTOS DO PROCESSO") if "MOVIMENTOS DO PROCESSO" in nao_vazias else 8
    cab = nao_vazias[:fim]
    ignorar = set(cab) | {"MOVIMENTOS DO PROCESSO"}
    raw_l = [l.strip() for l in raw.replace("\f", "\n").split("\n")]
    raw_l = [l for l in raw_l if l and l not in ignorar and not RODAPE.match(l)]
    lay_l = [l.rstrip() for l in lay.replace("\f", "\n").split("\n")]
    lay_l = [l for l in lay_l if l.strip() and l.strip() not in ignorar and not RODAPE_LAYOUT.match(l)]
    return raw_l, lay_l, cab


RE_EVENTO_LAY = re.compile(r"(?:^|\s)(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\s+[A-ZÀ-Ú]{2,}")
RE_ITEM_L = re.compile(r"^\s*Item:\s*(\d+)\s+Unidade:\s*(.*?)\s{2,}Marca:\s*(.*?)\s{2,}Modelo:\s*(.*)$")
RE_QTD_L = re.compile(r"Quantidade:\s*([\d.,]+)\s+Valor Unit\.:\s*([\d.,]+)\s+Valor Total:\s*([\d.,]+)")
RE_CLASS_L = re.compile(r"(\d{3})\s+(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+([\d.,]+)\s+([\d.,]+)(?:\s+([\d.,]+))?\s+(Sim|Não)\s*$")


def estrutura_layout(lay: list[str]) -> tuple[list[tuple[str, int | None]], list[dict]]:
    """Sequência (data/hora, índice do lote) de cada evento + dados de cada lote (itens e classificação)."""
    seq: list[tuple[str, int | None]] = []
    lotes: list[dict] = []
    tabela = None
    for l in lay:
        me = RE_EVENTO_LAY.search(l)  # no layout a data pode vir depois do fim de uma razão social quebrada
        if me:
            seq.append((iso(me.group(1)), len(lotes) - 1 if lotes else None))
            tabela = None
            continue
        ml = RE_LOTE.match(l)
        if ml:
            lotes.append({"lote": f"{ml.group(1).title()} {int(ml.group(2))}", "situacao": ml.group(3).strip(),
                          "itens": [], "classificacao": [], "desclassificados": [], "inabilitados": []})
            tabela = None
            continue
        if not lotes:
            continue
        t = l.strip()
        if t in ("CLASSIFICAÇÃO", "DESCLASSIFICADOS", "INABILITADOS"):
            tabela = {"CLASSIFICAÇÃO": "classificacao", "DESCLASSIFICADOS": "desclassificados",
                      "INABILITADOS": "inabilitados"}[t]
            continue
        mi = RE_ITEM_L.match(l)
        if mi:
            lotes[-1]["itens"].append({"item": int(mi.group(1)), "unidade": mi.group(2).strip(),
                                       "marca": mi.group(3).strip(), "modelo": mi.group(4).strip()})
            continue
        mq = RE_QTD_L.search(l)
        if mq and lotes[-1]["itens"]:
            lotes[-1]["itens"][-1].update(quantidade=valor(mq.group(1)), valor_unitario=valor(mq.group(2)),
                                          valor_total=valor(mq.group(3)))
            continue
        mc = RE_CLASS_L.search(l)
        if mc and tabela:
            pos = re.match(r"^\s*(\d+)\s", l)
            lotes[-1][tabela].append({"posicao": int(pos.group(1)) if pos else None, "participante": mc.group(1),
                                      "cnpj": mc.group(2), "oferta_inicial": valor(mc.group(3)),
                                      "oferta_final": valor(mc.group(4)), "dif_pct": valor(mc.group(5)),
                                      "me_epp": mc.group(6) == "Sim"})
    return seq, lotes


def meta_de(cab: list[str]) -> dict:
    m: dict = {"orgao": cab[0] if cab else None, "municipio_uf": cab[1] if len(cab) > 1 else None}
    for l in cab:
        for chave, rx in (("modalidade_numero", r"^(PREGÃO ELETRÔNICO|CONCORRÊNCIA|DISPENSA|CREDENCIAMENTO).*Nº\s*(\S+)"),
                          ("processo_adm", r"Processo Administrativo Nº\s*(\S+)"), ("tipo", r"^Tipo:\s*(.+)"),
                          ("pregoeiro", r"^(?:PREGOEIRO|AGENTE DE CONTRATAÇÃO):\s*(.+)"),
                          ("publicacao", r"Data de Publicação:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})")):
            mm = re.search(rx, l)
            if mm:
                m[chave] = mm.group(0 if chave == "modalidade_numero" else 1).strip()
    if m.get("publicacao"):
        m["publicacao"] = iso(m["publicacao"])
    return m


def separar(resto: str) -> tuple[str, str, float | None]:
    """'LANCE   EMPRESA (PARTICIPANTE 1)   207,00' -> (tipo, ator, valor)"""
    val = None
    if resto.startswith("LANCE "):
        v = RE_VALOR_FIM.search(resto)
        if v:
            val, resto = valor(v.group(1)), resto[: v.start()]
    resto = re.sub(r"\s+", " ", resto).strip()
    for t in sorted(TIPOS_COM_ATOR, key=len, reverse=True):
        if resto == t or resto.startswith(t + " "):
            return t, resto[len(t):].strip(), val
    return resto, "", val  # mudança de fase: PUBLICADO, DISPUTA, ADJUDICADO...


def autor_de(tipo: str, ator: str) -> str:
    a = ator.upper()
    if a in ("SISTEMA",) or tipo == "NOTIFICAÇÃO":
        return "sistema"
    if a.startswith("PREGOEIRO") or a.startswith("AGENTE") or a.startswith("COMISS"):
        return "pregoeiro"
    if tipo in ("LANCE", "RECURSO MANIFESTADO", "ESCLARECIMENTO REQUERIDO", "CADASTRO DE PROPOSTA",
                "ALTERAÇÃO DE PROPOSTA", "IMPUGNAÇÃO") or RE_PART.search(ator) or RE_CNPJ.search(ator):
        return "fornecedor"
    return "pregoeiro" if tipo.startswith(("RESPOSTA", "DESCLASSIFICAÇÃO", "INABILITAÇÃO")) else "indeterminado"


def eventos_raw(linhas: list[str]) -> list[dict]:
    eventos: list[dict] = []
    atual: dict | None = None
    for l in linhas:
        me = RE_EVENTO.match(l)
        if me:
            tipo, ator, val = separar(me.group(2))
            atual = {"em": iso(me.group(1)), "tipo": tipo, "ator": ator, "valor": val, "texto": ""}
            atual["_espera"] = (tipo in ESPERA_ATOR and ator and ator.upper() not in ("PREGOEIRO", "SISTEMA")
                                and not RE_FIM_ATOR.search(ator))
            eventos.append(atual)
            continue
        if RE_LOTE.match(l) or FECHA_TEXTO.match(l):  # tabela/cabeçalho de lote: não é texto do evento
            atual = None
            continue
        if atual is None:
            continue
        t = re.sub(r"\s+", " ", l).strip()
        if atual.get("_espera"):  # razão social quebrada: segue até "(PARTICIPANTE n)" ou "(CNPJ)"
            junto = f"{atual['ator']} {t}"
            mf = RE_FIM_ATOR.search(junto)  # inclui "(PARTICIPANTE" numa linha e "431)" na seguinte
            if mf and mf.end() > len(atual["ator"]):
                atual["ator"] = junto[: mf.end()].strip()
                t = junto[mf.end():].strip()
                atual["_espera"] = False
                if not t:
                    continue
            elif t.isupper() and len(t) < 90 and not RE_SO_VALOR.match(t):
                atual["ator"] = f"{atual['ator']} {t}".strip()
                continue
            else:
                atual["_espera"] = False
        if atual["tipo"] == "LANCE" and atual["valor"] is None:
            v = RE_SO_VALOR.match(t) or RE_VALOR_FIM.search(t)
            if v:
                atual["valor"] = valor(v.group(0).strip() if RE_SO_VALOR.match(t) else v.group(1))
                continue
        if atual["tipo"] == "LANCE" or (not atual["ator"] and atual["tipo"] not in CHAT):
            continue  # lance e mudança de fase não têm texto: o que vier é resto de tabela
        atual["texto"] = f"{atual['texto']} {t}".strip()
    for e in eventos:
        e.pop("_espera", None)
    return eventos


def extrair(pdf: Path) -> dict:
    raw, lay, cab = ler_linhas(pdf)
    meta = meta_de(cab)
    eventos = eventos_raw(raw)
    seq, lotes = estrutura_layout(lay)
    # alinha eventos do texto (-raw) com a estrutura (-layout) pela sequência de data/hora
    sm = difflib.SequenceMatcher(a=[t for t, _ in seq], b=[e["em"] for e in eventos], autojunk=False)
    lote_de: list[int | None] = [None] * len(eventos)
    casados = 0
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            for k in range(b2 - b1):
                lote_de[b1 + k] = seq[a1 + k][1]
            casados += b2 - b1
        else:  # trecho fora de ordem: herda o lote do evento anterior já casado
            for k in range(b1, b2):
                lote_de[k] = lote_de[k - 1] if k else None
    if eventos and casados / len(eventos) < 0.95:
        raise SystemExit(f"Só {casados}/{len(eventos)} eventos alinharam com a estrutura da página: "
                         "formato de ata diferente, revisar o parser.")
    eventos_processo: list[dict] = []
    for lt in lotes:
        lt.update(fases=[], lances=[], eventos=[])
    for idx, e in zip(lote_de, eventos):
        (eventos_processo if idx is None else lotes[idx]["eventos"]).append(e)
    meta["alinhamento"] = {"eventos": len(eventos), "casados": casados}
    nomes: dict[str, str] = {}
    for lt in lotes:
        for e in lt["eventos"]:
            if e["tipo"] == "LANCE":
                p = RE_PART.search(e["ator"])
                emp = RE_PART.sub("", e["ator"]).strip()
                if p:
                    nomes[p.group(1)] = emp
                lt["lances"].append({"em": e["em"], "empresa": emp, "participante": p.group(1) if p else None,
                                     "valor": e["valor"]})
            elif not e["ator"] and e["tipo"] not in CHAT:
                lt["fases"].append({"fase": e["tipo"], "em": e["em"]})
    for lt in lotes:  # nome limpo da empresa na classificação (no layout a razão social quebra em colunas)
        for tab in ("classificacao", "desclassificados", "inabilitados"):
            for c in lt[tab]:
                c["empresa"] = nomes.get(c["participante"])
    return {"meta": meta, "lotes": lotes, "eventos_processo": eventos_processo}


def chat_de(ata: dict, processo: str) -> list[dict]:
    saida = []
    todos = [(None, e) for e in ata["eventos_processo"]] + [(lt["lote"], e) for lt in ata["lotes"] for e in lt["eventos"]]
    todos.sort(key=lambda x: x[1]["em"])
    for seq, (lote, e) in enumerate(((l, e) for l, e in todos if e["tipo"] in CHAT), 1):
        empresa = RE_PART.sub("", RE_CNPJ.sub("", e["ator"])).strip() or None
        autor = autor_de(e["tipo"], e["ator"])
        saida.append({"id": f"bll-{processo}-{seq:05d}", "origem": "bll", "processo": processo, "seq": seq,
                      "data_hora_brasilia": e["em"], "tipo_evento": e["tipo"], "lote": lote,
                      "autor": autor, "autor_por": "ata",
                      "empresa": empresa if autor == "fornecedor" else None,
                      "cnpj": (RE_CNPJ.search(e["ator"]) or [None, None])[1] if RE_CNPJ.search(e["ator"]) else None,
                      "texto": e["texto"]})
    return saida


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Ata de Sessão da BLL -> JSON (lotes, lances) + chat JSONL")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--chat", type=Path)
    ap.add_argument("--processo", default="", help="identificador (ex.: codigo_externo do PNCP)")
    a = ap.parse_args(argv)
    ata = extrair(a.pdf)
    a.saida.write_text(json.dumps(ata, ensure_ascii=False, indent=1), encoding="utf-8")
    n_lances = sum(len(l["lances"]) for l in ata["lotes"])
    print(f"{ata['meta'].get('orgao')} | {ata['meta'].get('modalidade_numero')} | pregoeiro: {ata['meta'].get('pregoeiro')}")
    n_itens = sum(len(l["itens"]) for l in ata["lotes"])
    n_class = sum(len(l["classificacao"]) for l in ata["lotes"])
    print(f"{len(ata['lotes'])} lotes {dict(Counter(l['situacao'] for l in ata['lotes']))} | {n_lances} lances | "
          f"{n_itens} itens com marca/modelo/valor | {n_class} linhas de classificação | "
          f"{len(ata['eventos_processo'])} eventos antes dos lotes")
    if a.chat:
        chat = chat_de(ata, a.processo or a.pdf.stem)
        a.chat.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chat), encoding="utf-8")
        print(f"chat: {len(chat)} mensagens | autores {dict(Counter(c['autor'] for c in chat))} | "
              f"tipos {dict(Counter(c['tipo_evento'] for c in chat))}")
    print(f"-> {a.saida}")


if __name__ == "__main__":
    main()
