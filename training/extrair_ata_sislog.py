"""Extrai a "ATA - PREGÃO ELETRÔNICO" do SISLOG/GO (PDF impresso do portal) em JSON estruturado.

A ata do portal traz o que o PNCP não traz:
  - resumo por lote (situação, fornecedor aceito, valor);
  - por lote: participantes e propostas (CNPJ, porte, data/hora, valor ou "Não Enviado"),
    todos os lances com data/hora e CNPJ, desempate ME/EPP, lances e eventos de negociação;
  - troca de mensagens com o autor (Fornecedor, Agente de Contratação, Sistema...).

Por que o PDF e não só o HTML: no HTML o autor de ~40% das mensagens não é identificável; na ata cada mensagem
vem com o autor. O texto é lido com `pdftotext -raw` (o modo `-layout` corta as linhas longas na margem direita:
"Neste viés," virava "Nest").

Uso:
  python3 training/extrair_ata_sislog.py "ATA - PREGÃO ELETRÔNICO - SRP Nº 104744 - 3.pdf" --saida data/ata_104744.json
  python3 training/extrair_ata_sislog.py ata.pdf --saida ata.json --chat-html "html lang=enhead.txt"   # compara com o chat do HTML

Só lê arquivo local já baixado do portal público (sem login). Nada é inventado: campo ausente fica null.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

RE_RODAPE = re.compile(r"^(\d{2}/\d{2}/\d{4}, \d{2}:\d{2} Documento|about:blank \d+/\d+|Documento|https?://\S+ Página \d+ de \d+)$")
RE_LOTE = re.compile(r"^LOTE \((.+)\)(?: - (.+))?$")
# disputa por item (ex.: 111606): resumo "ITEM 002 - ADJUDICADO", bloco "ITEM - 002"
RE_ITEM_RESUMO = re.compile(r"^ITEM (\d{1,4}) - ([A-ZÀ-Ú ]+)$")
RE_ITEM_BLOCO = re.compile(r"^ITEM - (\d{1,4})$")
RE_LANCE_NEG = re.compile(r"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) (?:R\$ )?([\d.,]+)$")
RE_EVENTO_ITEM = re.compile(r"^(.+?) (\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})$")
RE_ACEITO_SO = re.compile(r"^Aceito para:\s*$")
RE_CNPJ_NOME = re.compile(r"^(\d{11,14})-(.+)$")
RE_PARTICIPANTE = re.compile(
    r"^(\d{11,14}) (.+?) - (ME|EPP|NO|DEMAIS|MEI)\s+(?:(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) R\$ ([\d.,]+)|Não Enviado Não Enviado)$")
RE_LANCE = re.compile(r"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) (\d{11,14}) (?:R\$ )?([\d.,]+)$")
RE_EVENTO = re.compile(r"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) (.+)$")
RE_DATA_FIM = re.compile(r"^(.*?)\s*(\d{2}/\d{2}/\d{4})$")
RE_HORA = re.compile(r"^(\d{2}:\d{2}:\d{2})(?: (.*))?$")
RE_ACEITO = re.compile(r"^Aceito para: (\d{11,14})-(.+)$")
RE_VALOR = re.compile(r"^Valor: R\$ ([\d.,]+)$")
RE_INICIO = re.compile(r"Às (\d{2}:\d{2}) horas do dia (\d{1,2}) de (\w+) de (\d{4}) iniciou-se a sessão")
MESES = {m: i for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}
AUTORES = ("fornecedor", "sistema", "pregoeiro", "agente de contratação", "agente de contratacao", "comprador",
           "administrador", "equipe de apoio", "autoridade competente")


def valor(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def iso(dh: str) -> str:
    """'31/07/2024 09:13:13' -> '2024-07-31T09:13:13-03:00' (horário de Brasília, como no portal)."""
    return datetime.strptime(dh, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S-03:00")


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


RE_DH_SO = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")


def linhas_html(bruto: str) -> list[str]:
    """Ata baixada pelo coletar_sislog.py (HTML do SISLOG): cada célula vem numa linha. Remonta as linhas no
    mesmo formato do pdftotext -raw para o resto do parser não mudar."""
    import html as _html
    h = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", bruto)
    h = re.sub(r"(?is)data:[a-z/]+;base64,[A-Za-z0-9+/=]+", " ", h)
    h = re.sub(r"\s+", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d|table|legend|fieldset|thead|tbody)>|<(tr|table|p|div|h\d)\b",
               "\n\\g<0>", h)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    cel = [re.sub(r"\s+", " ", l).strip() for l in t.split("\n")]
    cel = [l for l in cel if l]
    out: list[str] = []
    secao = None
    i, n = 0, len(cel)
    marcador = re.compile(r"^(TROCA DE MENSAGENS|PARTICIPANTES E PROPOSTAS|LANCES|Hist[óo]rico da Sess|LOTE \(|"
                          r"ITEM - \d|ITEM \d+ - |Eventos do|Argumentos da Negocia|Lance\(s\) de)")
    while i < n:
        l = cel[i]
        prox = cel[i + 1] if i + 1 < n else ""
        if marcador.match(prox) and not marcador.match(l):  # nunca colar uma célula num cabeçalho de seção
            out.append(l)
            i += 1
            continue
        if l == "TROCA DE MENSAGENS":  # daqui em diante cada mensagem já vem numa linha
            out.extend(cel[i:])
            break
        if l in ("PARTICIPANTES E PROPOSTAS", "LANCES") or l.startswith(("Argumentos da Negociação", "Eventos do",
                                                                           "Lance(s) de")):
            secao = l
        elif re.match(r"^(ITEM|LOTE)\b", l):
            secao = None
        if secao == "PARTICIPANTES E PROPOSTAS" and re.fullmatch(r"\d{11,14}", l) and i + 3 < n:
            out.append(" ".join(cel[i:i + 4]))  # CNPJ | razão social - porte | data/hora | valor
            i += 4
            continue
        if secao and secao.startswith("Argumentos") and RE_DH_SO.match(l) and i + 1 < n:
            out.append(f"{l} {cel[i + 1]}")  # data/hora | texto do argumento
            i += 2
            continue
        if secao and secao.startswith("Eventos do") and i + 1 < n and (
                RE_DH_SO.match(cel[i + 1]) or re.fullmatch(r"x{5,}|Sim|Não", cel[i + 1])):
            out.append(f"{l} {cel[i + 1]}")  # evento | data/hora
            i += 2
            continue
        if l.endswith(":") and i + 1 < n and not cel[i + 1].endswith(":") and secao is None \
                and not re.match(r"^(ITEM|LOTE)\b|^Hist[óo]rico|^Benef[íi]cio", cel[i + 1]):
            out.append(f"{l} {cel[i + 1]}")  # "Valor Estimado:" | "912,02"
            i += 2
            continue
        out.append(l)
        i += 1
    return out


def texto_pdf(pdf: Path) -> list[str]:
    if pdf.suffix.lower() in (".html", ".htm"):
        return linhas_html(pdf.read_text(encoding="utf-8", errors="replace"))
    if pdf.suffix.lower() == ".txt":
        bruto = pdf.read_text(encoding="utf-8", errors="replace")
    else:
        bruto = subprocess.run(["pdftotext", "-raw", "-enc", "UTF-8", str(pdf), "-"],
                               check=True, capture_output=True, text=True).stdout
    linhas = []
    for linha in bruto.replace("\f", "\n").split("\n"):
        linha = re.sub(r"\s+", " ", linha).strip()
        if linha and not RE_RODAPE.match(linha):
            linhas.append(linha)
    return linhas


RE_SO_DATA = re.compile(r"^(.*?)\s*(\d{2}/\d{2}/\d{4})$")
RE_CNPJ_VALOR = re.compile(r"^\d{11,14} (?:R\$ )?[\d.,]+$")


def juntar(linhas: list[str]) -> list[str]:
    """Une 'dd/mm/aaaa' + 'hh:mm:ss ...' (o PDF quebra a coluna DATA/HORA em duas linhas, em alguns processos
    também 'data hora' + 'CNPJ valor' do lance). Resultado: 'prefixo dd/mm/aaaa hh:mm:ss resto'."""
    saida: list[str] = []
    i = 0
    while i < len(linhas):
        l = linhas[i]
        md = RE_SO_DATA.match(l)
        if md and i + 1 < len(linhas) and RE_HORA.match(linhas[i + 1]):
            mh = RE_HORA.match(linhas[i + 1])
            l = " ".join(x for x in (md.group(1), md.group(2), mh.group(1), mh.group(2) or "") if x)
            i += 1
            if re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}", l) and i + 1 < len(linhas) \
                    and RE_CNPJ_VALOR.match(linhas[i + 1]):
                l = f"{l} {linhas[i + 1]}"
                i += 1
        saida.append(l)
        i += 1
    return saida


def extrair(linhas: list[str]) -> dict:
    linhas = juntar(linhas)
    meta: dict = {"titulo": linhas[2] if len(linhas) > 2 else None}
    corpo = " ".join(linhas[:40])
    m = RE_INICIO.search(corpo)
    if m:
        mes = MESES.get(norm(m.group(3)))
        if mes:
            meta["inicio_sessao"] = f"{m.group(4)}-{mes:02d}-{int(m.group(2)):02d}T{m.group(1)}:00-03:00"
    for chave, rx in (("numero", r"de número nº (\d+)"), ("sequencial", r"sequencial (\S+?),"),
                      ("processo_sei", r"processo SEI nº (\d+)")):
        mm = re.search(rx, corpo)
        meta[chave] = mm.group(1) if mm else None

    resumo: list[dict] = []
    lotes: list[dict] = []
    mensagens: list[dict] = []
    i, n = 0, len(linhas)
    secao = "cabecalho"
    lote = None
    sub = None

    while i < n:
        l = linhas[i]
        if l == "TROCA DE MENSAGENS":
            secao, i = "mensagens", i + 1
            break
        ml = RE_LOTE.match(l)
        mir, mib = RE_ITEM_RESUMO.match(l), RE_ITEM_BLOCO.match(l)
        if mir and secao in ("cabecalho", "resumo"):
            ml = mir
        elif mib:
            ml = mib
        if ml:
            nome = f"Item {int(ml.group(1)):03d}" if (mir or mib) else ml.group(1)
            situacao = ml.group(2) if (ml is not mib and ml.lastindex and ml.lastindex >= 2) else None
            if situacao is not None and secao in ("cabecalho", "resumo"):
                secao = "resumo"
                item = {"lote": nome, "situacao": situacao, "aceito_cnpj": None, "aceito_nome": None, "valor": None}
                resumo.append(item)
                lote = item
            else:
                secao, sub = "lotes", None
                lote = {"lote": nome, "participantes": [], "lances": [], "desempate": [],
                        "negociacao_lances": [], "negociacao_eventos": []}
                lotes.append(lote)
            i += 1
            continue
        if secao == "resumo" and lote is not None:
            ma, mv = RE_ACEITO.match(l), RE_VALOR.match(l)
            if ma:
                lote["aceito_cnpj"], lote["aceito_nome"] = ma.group(1), ma.group(2).strip()
            elif RE_ACEITO_SO.match(l) and i + 1 < n and RE_CNPJ_NOME.match(linhas[i + 1]):
                mc = RE_CNPJ_NOME.match(linhas[i + 1])
                nome_emp, j = mc.group(2).strip(), i + 2
                while j < n and not linhas[j].startswith(("Período:", "Marca:", "Valor")):  # nome em 2+ linhas
                    nome_emp += " " + linhas[j]
                    j += 1
                lote["aceito_cnpj"], lote["aceito_nome"] = mc.group(1), nome_emp
                i = j
                continue
            elif mv:
                lote["valor"] = valor(mv.group(1))
            else:
                for chave, rx in (("valor_estimado", r"Valor Estimado: (?:R\$ )?([\d.,]+)"),
                                  ("valor", r"Valor Unitário: R\$ ([\d.,]+)"),
                                  ("valor_total", r"Valor Total: R\$ ([\d.,]+)"),
                                  ("quantidade", r"Quantidade: (\d[\d.]*) ")):
                    mm2 = re.search(rx, l)
                    if mm2:
                        lote[chave] = valor(mm2.group(1))
        elif secao == "lotes" and lote is not None:
            if l == "PARTICIPANTES E PROPOSTAS":
                sub = "participantes"
            elif l == "LANCES":
                sub = "lances"
            elif l.startswith("Lance(s) de desempate"):
                sub = "desempate"
            elif l.startswith("Lance(s) de negociação"):
                sub = "negociacao_lances"
            elif l.startswith("Argumentos da Negociação"):
                sub = "negociacao_eventos"
            elif l.startswith("Eventos do Item") or l.startswith("Eventos do Lote"):
                sub = "eventos"
                lote.setdefault("eventos", [])
            elif sub == "eventos":
                me2 = RE_EVENTO_ITEM.match(l)
                if me2 and not re.search(r"(até:|^\(|^-)", me2.group(1)):
                    lote["eventos"].append({"evento": me2.group(1), "em": iso(me2.group(2))})
            elif sub == "participantes":
                mp = RE_PARTICIPANTE.match(l)
                if mp:
                    lote["participantes"].append({
                        "cnpj": mp.group(1), "nome": mp.group(2).strip(), "porte": mp.group(3),
                        "enviada_em": iso(mp.group(4)) if mp.group(4) else None,
                        "valor_proposta": valor(mp.group(5)), "enviou": mp.group(4) is not None})
            elif sub in ("lances", "desempate", "negociacao_lances"):
                mx = RE_LANCE.match(l)
                if mx:
                    lote[sub].append({"em": iso(mx.group(1)), "cnpj": mx.group(2), "valor": valor(mx.group(3))})
                elif sub == "negociacao_lances" and RE_LANCE_NEG.match(l):  # por item a ata omite o CNPJ
                    mn = RE_LANCE_NEG.match(l)
                    lote[sub].append({"em": iso(mn.group(1)), "cnpj": None, "valor": valor(mn.group(2))})
            elif sub == "negociacao_eventos":
                me = RE_EVENTO.match(l)
                if me:
                    lote["negociacao_eventos"].append({"em": iso(me.group(1)), "texto": me.group(2)})
                elif lote["negociacao_eventos"]:
                    lote["negociacao_eventos"][-1]["texto"] += " " + l
        i += 1

    # Mensagens: [autor (1-2 linhas)] dd/mm/aaaa hh:mm:ss [texto...] até o próximo cabeçalho
    re_msg = re.compile(r"^(.*?)\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})(?: (.*))?$")
    pend_autor: list[str] = []
    atual = None
    while i < n:
        l = linhas[i]
        mm = re_msg.match(l)
        if mm:
            cand = " ".join(pend_autor + ([mm.group(1)] if mm.group(1) else [])).strip()
            if cand == "" or norm(cand) in AUTORES or norm(cand).startswith(AUTORES):
                if atual:
                    mensagens.append(atual)
                atual = {"em": iso(mm.group(2)), "autor": cand or None, "texto": (mm.group(3) or "").strip()}
                pend_autor = []
                i += 1
                continue
        # autor em duas linhas ("Agente de" / "Contratação"), antes da linha da data
        if norm(l) in ("agente de", "equipe de", "autoridade") and i + 1 < n:
            pend_autor = [l]
            i += 1
            continue
        if pend_autor and norm(l) in ("contratacao", "apoio", "competente"):
            pend_autor.append(l)
            i += 1
            continue
        if norm(l) in ("fornecedor", "sistema", "pregoeiro") and i + 1 < n and re_msg.match(linhas[i + 1]):
            pend_autor = [l]
            i += 1
            continue
        if pend_autor:  # não era autor: devolve ao texto
            l = " ".join(pend_autor + [l])
            pend_autor = []
        if atual is not None:
            atual["texto"] = (atual["texto"] + " " + l).strip()
        i += 1
    if atual:
        mensagens.append(atual)
    # rodapé de assinatura da ata não é mensagem
    if mensagens and "nada mais havendo" in norm(mensagens[-1]["texto"]):
        mensagens[-1]["texto"] = re.split(r"\s*Essa sessão foi conduzida", mensagens[-1]["texto"])[0]
    return {"meta": meta, "resumo": resumo, "lotes": lotes, "mensagens": mensagens}


def resumo_lotes(ata: dict) -> list[dict]:
    est = {}
    for m in ata["mensagens"]:  # valores estimados publicados no chat ("Lote 01: ... R$ 296.622,00")
        for lt, v in re.findall(r"Lote (\d{1,2}):[^R]*?R\$ ([\d.,]+)", m["texto"]):
            est.setdefault(int(lt), valor(v))
    saida = []
    estimado_resumo = {r["lote"]: r.get("valor_estimado") for r in ata["resumo"]}
    for lote in ata["lotes"]:
        num = re.match(r"Lote:? ?(\d+)", lote["lote"])
        k = int(num.group(1)) if num else lote["lote"]
        if estimado_resumo.get(lote["lote"]) is not None:
            est.setdefault(k, estimado_resumo[lote["lote"]])
        lances = [x["valor"] for x in lote["lances"] + lote["negociacao_lances"] if x["valor"]]
        enviadas = [p for p in lote["participantes"] if p["enviou"]]
        saida.append({
            "lote": lote["lote"], "participantes": len(lote["participantes"]), "propostas": len(enviadas),
            "lances": len(lote["lances"]), "estimado": est.get(k),
            "menor": min(lances) if lances else None,
            "queda_vs_estimado": round(1 - min(lances) / est[k], 3) if lances and est.get(k) else None,
        })
    return saida


def comparar_html(ata: dict, chat_jsonl: Path) -> dict:
    """Compara com a saída do rotular_chat.py (mesmo processo): casa por data/hora até o minuto + início do texto."""
    html = [json.loads(x) for x in chat_jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
    chave = lambda em, t: (em[:16], norm(re.sub(r"\s+", " ", t))[:40])  # noqa: E731
    ata_k = Counter(chave(m["em"], m["texto"]) for m in ata["mensagens"])
    html_k = Counter(chave(m["data_hora_brasilia"], m["texto"]) for m in html)
    comum = sum((ata_k & html_k).values())
    autores_html_sem = sum(1 for m in html if m.get("autor") in (None, "indeterminado"))
    return {"mensagens_ata": len(ata["mensagens"]), "mensagens_html": len(html), "casadas": comum,
            "so_ata": sum((ata_k - html_k).values()), "so_html": sum((html_k - ata_k).values()),
            "html_sem_autor": autores_html_sem,
            "ata_autores": dict(Counter(m["autor"] for m in ata["mensagens"]))}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--chat-jsonl", type=Path, help="saída do rotular_chat.py do mesmo processo, para comparar")
    a = ap.parse_args(argv)
    ata = extrair(texto_pdf(a.pdf))
    ata["resumo_lotes"] = resumo_lotes(ata)
    a.saida.write_text(json.dumps(ata, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"processo {ata['meta'].get('numero')} | início {ata['meta'].get('inicio_sessao')} | "
          f"{len(ata['resumo'])} lotes no resumo | {len(ata['lotes'])} blocos de lote | "
          f"{sum(len(l['lances']) for l in ata['lotes'])} lances | {len(ata['mensagens'])} mensagens")
    print("situação:", dict(Counter(r["situacao"] for r in ata["resumo"])))
    print("autores:", dict(Counter(m["autor"] for m in ata["mensagens"])))
    if a.chat_jsonl:
        print("comparação com o HTML:", json.dumps(comparar_html(ata, a.chat_jsonl), ensure_ascii=False))
    print(f"-> {a.saida}")


if __name__ == "__main__":
    sys.exit(main())
