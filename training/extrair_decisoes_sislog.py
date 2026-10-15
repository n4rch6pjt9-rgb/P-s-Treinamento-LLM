#!/usr/bin/env python3
"""Decisões técnicas e recursais de um pregão SISLOG/GO em exemplos de treinamento (JSONL).

Lê a pasta baixada do processo (PDFs ou .txt já extraídos) e gera um registro por decisão:

* exequibilidade: relatórios da comissão ("RELATÓRIO [FINAL] Nº n / aaaa"), um registro por lote e empresa;
* recurso: "RESPOSTA AO RECURSO" / "JULGAMENTO RECURSO ADMINISTRATIVO" da agente de contratação;
* manifestacao_autoridade: julgamento da autoridade superior (lotes com recurso, deferidos, improcedentes).

Cada item citado é ligado à descrição do Termo de Referência (lote, código, especificação, valor estimado),
para o agente aprender "o que o TR pedia" x "o que foi ofertado" x "o que a comissão decidiu".

Regra da casa: nada é inventado. Se o documento não diz a empresa (relatórios-resumo "LOTE 2: APROVADO"),
`empresa` fica null; o cruzamento com a ata fica para outra etapa, com a fonte registrada.

Uso:
    python3 training/extrair_decisoes_sislog.py --pasta "<pasta do processo>" --processo 104744 \
        --saida training/data/decisoes_104744.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

VERSAO = "2026-10-15"
URL_PROCESSO = "https://sislog.go.gov.br/PanelAquisicao/DetalhesLicitacao?idLicitacao={}"
MESES = {m: i for i, m in enumerate(
    "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}


# --------------------------------------------------------------------------- texto
def ascii_lower(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def ler(caminho: Path) -> str:
    if caminho.suffix.lower() == ".pdf":
        r = subprocess.run(["pdftotext", "-layout", str(caminho), "-"], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"pdftotext falhou em {caminho.name}: {r.stderr.strip()}")
        return r.stdout
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    if caminho.suffix.lower() in (".html", ".htm"):  # documento baixado pelo coletar_sislog.py
        return html_para_texto(texto)
    return texto


def html_para_texto(h: str) -> str:
    import html as _html
    h = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", h)
    h = re.sub(r"(?is)data:[a-z/]+;base64,[A-Za-z0-9+/=]+", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d|table|legend|fieldset)>", "\n", h)
    h = re.sub(r"(?i)</t[dh]>", "  ", h)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in t.splitlines())


RUIDO = re.compile(
    r"^\s*(about:blank.*|\d\d/\d\d/\d{4}, \d\d:\d\d.*|SEI/GOVERNADORIA.*|https?://sei\.go\.gov\.br\S*.*|"
    r"Documento assinado eletronicamente.*|Superintendente, em .*|.*conforme art\. 2º.*|.*8\.808/2016\.|"
    r"A autenticidade do documento.*|.*controlador_externo.*|.*acao=documento_conferir.*|"
    r"\d{8} e o código CRC.*|Referência: Processo.*)$", re.M)


def limpo(t: str) -> str:
    return RUIDO.sub("", t)


def junta(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def data_extenso(t: str) -> str | None:
    m = re.search(r"(?:GOI[AÂ]NIA|Goi[aâ]nia)\s*,\s*(\d{1,2}) de ([a-zç]+) de (\d{4})", t, re.I)
    if not m:
        return None
    mes = MESES.get(ascii_lower(m.group(2)))
    return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}" if mes else None


def sei(t: str) -> str | None:
    m = re.search(r"SEI/GOVERNADORIA - (\d{7,9})", t) or re.search(r"\bSEI (\d{7,9})\b", t)
    return m.group(1) if m else None


# --------------------------------------------------------------------------- Termo de Referência
ITEM_TR = re.compile(
    r"(?:Lote (\d+)\s*[:–-]\s*([^\n]+?)\n\s*)?Descrição do item (\d{3})\s*\n(.*?)Valor Unitário\s+R\$\s*([\d.,]+)", re.S)
# pregão por item (SES-GO) não tem "Lote n:" antes do item: lote fica null


def carregar_tr(texto: str) -> dict[int, dict]:
    """item (int) -> {lote, lote_titulo, codigo, catalogo, especificacao, quantidade, unidade, valor_unitario}"""
    itens: dict[int, dict] = {}
    for m in ITEM_TR.finditer(limpo(texto)):
        corpo = m.group(4)
        cod = re.search(r"Código\s+(\d+)\s*-\s*(.*?)Informações Adicionais", corpo, re.S)
        esp = re.search(r"Informações Adicionais(.*?)Período", corpo, re.S)
        qtd = re.search(r"Quantidade\s+([\d.]+)", corpo)
        und = re.search(r"Unidade\s+(\S.*)", corpo)
        itens[int(m.group(3))] = {
            "lote": int(m.group(1)) if m.group(1) else None,
            "lote_titulo": junta(m.group(2)) if m.group(2) else None,
            "codigo": cod.group(1) if cod else None,
            "catalogo": junta(cod.group(2)) if cod else None,
            "especificacao": junta(esp.group(1)) if esp else None,
            "quantidade": int(qtd.group(1).replace(".", "")) if qtd else None,
            "unidade": junta(und.group(1)) if und else None,
            "valor_unitario": float(m.group(5).replace(".", "").replace(",", ".")),
        }
    return itens


def itens_do_lote(tr: dict[int, dict], lote: int) -> list[int]:
    return sorted(i for i, d in tr.items() if d["lote"] == lote)


def itens_citados(texto: str, validos: list[int]) -> list[int]:
    """Números no texto que são itens do lote (evita confundir '24 gomos' ou '0%' com item)."""
    achados = {int(n) for n in re.findall(r"\b(\d{2,3})\b", texto)}
    return sorted(achados & set(validos))


# --------------------------------------------------------------------------- classificação de motivo
CATEGORIAS = [
    ("valor_inexequivel", r"inexequ"),
    ("certificacao_ausente", r"fivb|fih\b|selo|certifica|aprova[cç][aã]o d[ao]"),
    ("marca_modelo_ausente", r"marca e modelo|sem maiores especifica"),
    ("documento_orgao_errado", r"org[aã]o divergente"),
    ("especificacao_divergente", r"diverg|gomos|costurad|absor[cç]|n[aã]o atende|especifica[cç][aã]o divergente"),
    ("sem_razoes_recursais", r"deixou de encaminhar|aus[eê]ncia de raz|n[aã]o houve o envio"),
]


def categorias(texto: str) -> list[str]:
    a = ascii_lower(texto)
    if "orgao divergente" in a:  # documento enviado ao órgão errado não é divergência de especificação
        a = a.replace("orgao divergente", "orgao_divergente")
        return ["documento_orgao_errado"] + [n for n, rx in CATEGORIAS[:-2] if n != "documento_orgao_errado"
                                            and re.search(ascii_lower(rx), a)]
    return [nome for nome, rx in CATEGORIAS if re.search(ascii_lower(rx), a)]


def decisao_trecho(t: str) -> str | None:
    a = ascii_lower(t)
    if re.search(r"nao reprova|nao merece prosperar|cumpre todos|de acordo com o termo|nao devera ser fracassado", a):
        return "aprovado"
    if re.search(r"reprov|recusad|diverge|nao atende|nao possui|nao consta|sem aprovacao|desclassific", a):
        return "reprovado"
    if re.search(r"aprovad|equivalentes", a):
        return "aprovado"
    return None


def decisao_por_item(texto: str, validos: list[int], ultimo_vence: bool = False) -> dict[str, str]:
    """Quebra em orações (; e .) e decide cada item citado pela oração em que aparece.
    ultimo_vence: em resposta a recurso, a primeira menção é a alegação do recorrente e a última é a decisão."""
    saida: dict[str, str] = {}
    oracoes = re.split(r";|\.(?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", texto)
    for o in oracoes:
        d = decisao_trecho(o)
        if not d:
            continue
        for i in itens_citados(o, validos):
            if ultimo_vence:
                saida[f"{i:03d}"] = d
            else:
                saida.setdefault(f"{i:03d}", d)
    return saida


# --------------------------------------------------------------------------- relatórios de exequibilidade
RE_EMPRESA = re.compile(r"\b[Aa] [Ee]mpresa\s+(.+?)\s+(?:teve|apresentou|a\s?presentou)\b", re.S)
RE_RESUMO = re.compile(r"^(APROVADO|RECUSADO)\s*(?:-\s*(.*))?$", re.S)


def contexto_relatorio(corpo: str) -> str:
    a = ascii_lower(corpo)
    if "recurso" in a:
        return "recurso"
    if "remanescente" in a:
        return "remanescente"
    return "analise_inicial"


def extrair_relatorio(texto: str, tr: dict[int, dict]) -> list[dict]:
    t = limpo(texto)
    num = re.search(r"RELAT[ÓO]RIO( FINAL)?\s+N[ºo°]\s*(\d+)\s*/\s*(\d{4})", t)
    ini = re.search(r"\(SEEL\)\.", t)
    fim = re.search(r"Diante do exposto|Por ser verdade|\n\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ ]{14,}\n", t[ini.end():] if ini else t)
    corpo = (t[ini.end():] if ini else t)
    corpo = corpo[: fim.start()] if fim else corpo
    base = {
        "relatorio": f"{num.group(2)}/{num.group(3)}" + (" final" if num and num.group(1) else "") if num else None,
        "data": data_extenso(t),
        "contexto": contexto_relatorio(corpo),
    }
    rec = re.search(r"interposto pela empresa\s+(.+?)\.\s", junta(corpo))
    if rec:
        base["recorrente"] = rec.group(1)

    saida = []
    partes = re.split(r"\bLOTE\s+(\d+)\s*:", corpo)
    for lote_txt, bloco in zip(partes[1::2], partes[2::2]):
        lote = int(lote_txt)
        validos = itens_do_lote(tr, lote)
        bloco_j = junta(bloco)
        resumo = RE_RESUMO.match(bloco_j)
        if resumo:  # "LOTE 2: RECUSADO - VALORES INEXEQUÍVEL": não diz empresa nem item
            motivo = resumo.group(2) or None
            saida.append({**base, "lote": lote, "empresa": None, "itens": validos,
                          "decisao": "aprovado" if resumo.group(1) == "APROVADO" else "reprovado",
                          "decisao_por_item": {}, "motivo": motivo,
                          "categorias": categorias(motivo or ""), "item_citado_no_documento": False})
            continue
        # narrativo: pode ter mais de uma empresa no mesmo lote
        blocos = [b for b in re.split(r"(?=\b[Aa] [Ee]mpresa\s)", bloco_j) if b.strip()]
        for b in blocos:
            emp = RE_EMPRESA.search(b)
            citados = itens_citados(b, validos)
            por_item = decisao_por_item(b, validos)
            if por_item:
                decisao = "reprovado" if "reprovado" in por_item.values() else "aprovado"
            else:
                decisao = decisao_trecho(b)
                if decisao and citados:  # ex.: "os itens 076 (...) e 079 (...), são divergentes"
                    por_item = {f"{i:03d}": decisao for i in citados}
            saida.append({**base, "lote": lote, "empresa": junta(emp.group(1)) if emp else None,
                          "itens": citados or validos, "decisao": decisao, "decisao_por_item": por_item,
                          "motivo": b, "categorias": categorias(b), "item_citado_no_documento": bool(citados)})
    return saida


# --------------------------------------------------------------------------- recursos
def _parte(t: str, rotulo: str) -> tuple[str | None, str | None]:
    m = re.search(rf"{rotulo}:\s*(.+?)(?:\n\s*\n|\n\s*Recorrid|\n\s*I\s*[-–])", t, re.S)
    if not m:
        return None, None
    v = junta(m.group(1))
    cnpj = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", v)
    nome = re.split(r"\s*-\s*CNPJ", v)[0].strip()
    return nome, cnpj.group(0) if cnpj else None


def extrair_recurso(texto: str, tr: dict[int, dict]) -> list[dict]:
    t = limpo(texto)
    tj = junta(t)
    lote_m = re.search(r"[Ll]ote\s+0?(\d+)", tj)
    lote = int(lote_m.group(1)) if lote_m else None
    validos = itens_do_lote(tr, lote) if lote else []
    recorrente, cnpj_rte = _parte(t, "Recorrente")
    recorrente_descricao = None
    if recorrente and not cnpj_rte and re.match(r"manifesta", ascii_lower(recorrente)):
        recorrente_descricao, recorrente = recorrente, None  # o documento não nomeia o recorrente
    recorrida, cnpj_rda = _parte(t, "Recorrid[ao]")
    analise = re.search(r"AN[ÁA]LISE RECURSAL(.*?)(?:I{1,3}V?\s*[-–]\s*DAS CONTRARRAZ|II\s*-\s*DA DECIS)", tj)
    analise_txt = analise.group(1).strip() if analise else None
    dec = re.search(r"DA DECIS[ÃA]O(.*?)(?:Goi[âa]nia,|$)", tj)
    dec_txt = dec.group(1).strip() if dec else ""
    a = ascii_lower(dec_txt)
    if "sem efeito" in a or "ausencia de razoes" in a:
        decisao = "sem_razoes"
    elif re.search(r"\bdeferid|\bprovid|procedente", a) and not re.search(r"indeferid|improvid|improcedente", a):
        decisao = "provido"
    elif re.search(r"indeferid|improvid|improcedente", a):
        decisao = "improvido"
    else:
        decisao = None
    por_item = {}
    if analise_txt:
        for k, v in decisao_por_item(analise_txt, validos, ultimo_vence=True).items():
            # na voz do recurso: item "reprovado" = argumento do recorrente procede
            por_item[k] = "procede" if v == "reprovado" else "nao_procede"
    contrarrazoes = re.search(r"DAS CONTRARRAZ[ÕO]ES(.*?)(?:I{1,3}V?\s*[-–]\s*DA DECIS|$)", tj)
    return [{
        "data": data_extenso(t), "lote": lote, "recorrente": recorrente, "recorrente_descricao": recorrente_descricao,
        "cnpj_recorrente": cnpj_rte,
        "recorrida": recorrida, "cnpj_recorrida": cnpj_rda, "decisao": decisao,
        "argumento_por_item": por_item, "itens": itens_citados(analise_txt or "", validos) or validos,
        "fundamentacao": analise_txt, "contrarrazoes": junta(contrarrazoes.group(1)) if contrarrazoes else None,
        "dispositivo": dec_txt or None, "categorias": categorias(tj),
        "tempestivo": bool(re.search(r"tempestiv", ascii_lower(tj))),
    }]


# --------------------------------------------------------------------------- autoridade superior
def _lotes(trecho: str) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\b(\d{1,2})\b", trecho)})


def extrair_manifestacao(texto: str, tr: dict[int, dict]) -> list[dict]:
    tj = junta(limpo(texto))
    def grupo(rx: str) -> list[int]:
        m = re.search(rx, tj, re.I)
        return _lotes(m.group(1)) if m else []
    autoridade = re.search(r"SECRET[ÁA]RIO\s+([A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúâêôãõç ]+?)\s+nomead", tj)
    erros = [re.sub(r"^.*?\b(?=(?:Entretanto|Contudo|Todavia|Porém|Ocorre que)\b)", "", m.group(0)).strip()
             for m in re.finditer(
        r"(?:Entretanto|Contudo|Todavia|Porém|Ocorre que)?[^.]{0,80}?por equ[ií]voco.*?\.(?=\s+[A-ZÁÉÍÓÚ])", tj)]
    return [{
        "data": data_extenso(texto),
        "autoridade": autoridade.group(1).strip() if autoridade else None,
        "lotes_com_recurso": grupo(r"interposi[çc][ãa]o de recursos nos\s+lotes ([\d,\s e]+)"),
        "lotes_sem_razoes": grupo(r"nos lotes ([\d,\s e]+?)\s+embora tenha havido manifesta"),
        "lotes_deferidos": grupo(r"Foram deferidos:\s*lotes ([\d,\s e]+)"),
        "lotes_improcedentes": grupo(r"improcedentes, quais sejam\s*;?\s*lotes ([\d,\s e]+)"),
        "desclassificadas_por_recurso": [e.strip() for x in re.findall(
            r"desclassifica[çc][ãa]o das empresas ([A-Z][\w ]+? e [A-Z][\w ]+?),", tj) for e in re.split(r",| e ", x)],
        "erros_administrativos_reconhecidos": erros,
        "decisao": "mantida_decisao_pregoeira" if re.search(r"manuten[çc][ãa]o da decis", tj, re.I) else None,
    }]


# --------------------------------------------------------------------------- parecer técnico (SES-GO)
RE_EMPRESA_PARECER = re.compile(r"^\s*(?:[A-Z]\)\s*)?Empresa:\s*(.+?)\s*$", re.M)
RE_ITEM_PARECER = re.compile(r"^\s*Item (\d{1,3}):\s*", re.M)


def opcionais_tr(especificacao: str | None) -> list[str]:
    """Trechos que o próprio TR marca como opcionais ('opcional conectividade via bluetooth')."""
    if not especificacao:
        return []
    return [junta(x) for x in re.findall(r"\bopciona(?:l|is)\s+([^.;,]+)", especificacao, re.I)]


def alerta_opcional(motivo: str, especificacao: str | None) -> list[str]:
    """Motivo de reprovação que cita requisito opcional no TR: possível julgamento em desacordo com o edital."""
    alertas = []
    m = ascii_lower(motivo)
    todas_chaves: list[str] = []
    for trecho in opcionais_tr(especificacao):
        chaves = [w for w in re.findall(r"[a-z]{5,}", ascii_lower(trecho)) if w not in ("opcional", "via")]
        todas_chaves += chaves
        if any(c in m for c in chaves):
            alertas.append(f"motivo cita requisito que o TR marca como opcional: 'opcional {trecho}'")
    if alertas:
        # "não possui X, Y e Z": se todas as faltas apontadas são opcionais, a reprovação não tem outro fundamento
        faltas = re.findall(r"nao (?:possui|apresenta|tem)\s+(.+?)(?:,? portanto|\.|$)", m)
        partes = [p for f in faltas for p in re.split(r",|\s+e\s+", f) if p.strip()]
        outras = re.search(r"diverge|inconformidade|superior|inferior|fora d", m)
        if partes and not outras and all(any(c in p for c in todas_chaves) for p in partes):
            alertas.append("único motivo apontado é requisito opcional: possível desclassificação sem amparo no TR")
    return alertas


def extrair_parecer(texto: str, tr: dict[int, dict]) -> list[dict]:
    t = limpo(texto)
    fim = re.search(r"Versão do Doc\. Padrão|Diante do exposto|Retornem os autos", t)
    corpo_total = t
    t = t[: fim.start()] if fim and RE_EMPRESA_PARECER.search(t[: fim.start()]) else t
    conclusao = junta(corpo_total[fim.start():]) if fim else None
    saida = []
    emps = list(RE_EMPRESA_PARECER.finditer(t))
    for k, me in enumerate(emps):
        bloco = t[me.end(): emps[k + 1].start() if k + 1 < len(emps) else len(t)]
        itens = list(RE_ITEM_PARECER.finditer(bloco))
        for j, mi in enumerate(itens):
            motivo = junta(bloco[mi.end(): itens[j + 1].start() if j + 1 < len(itens) else len(bloco)])
            motivo = re.split(r"\s*Retornem os autos", motivo)[0]
            a = ascii_lower(motivo)
            if re.search(r"\bnao (atende|possui|apresenta)|diverge|inconformidade", a):
                decisao = "reprovado"
            elif re.search(r"\batende", a):
                decisao = "aprovado"
            else:
                decisao = None
            item = int(mi.group(1))
            esp = tr.get(item, {}).get("especificacao")
            saida.append({"data": data_extenso(texto), "empresa": junta(me.group(1)), "lote": tr.get(item, {}).get("lote"),
                          "itens": [item], "decisao": decisao, "decisao_por_item": {f"{item:03d}": decisao},
                          "motivo": motivo, "categorias": categorias(motivo) if decisao == "reprovado" else [],
                          "fonte_externa": re.findall(r"https?://\S+", corpo_total) or None,
                          "alertas": alerta_opcional(motivo, esp) if decisao == "reprovado" else [],
                          "conclusao": conclusao})
    return saida


def datar_pelo_chat(reg: dict, chat: list[dict]) -> None:
    """Parecer sem data: usa a 1ª mensagem do chat que publica a decisão (empresa + item)."""
    if reg.get("data") or not chat or not reg.get("empresa"):
        return
    chave = ascii_lower(reg["empresa"]).split()[0]
    itens = {int(i) for i in reg.get("itens") or []}
    for m in chat:
        t = ascii_lower(m.get("texto", ""))
        if not ("parecer" in t or "desclassific" in t or "habilitad" in t):
            continue
        for pos in (x.start() for x in re.finditer(re.escape(chave), t)):
            janela = t[pos: pos + 220]  # itens citados logo depois do nome da empresa
            janela = re.split(r";|\ba empresa\b", janela[len(chave):])[0]
            nums = {int(n) for lista in re.findall(r"\bite(?:m|ns) \(?([\d ,e]+)", janela)
                    for n in re.findall(r"\d{1,3}", lista)}
            if itens & nums:
                reg["publicado_no_chat_em"] = m.get("data_hora_brasilia")
                return


# --------------------------------------------------------------------------- roteamento
def tipo_documento(texto: str) -> str | None:
    a = ascii_lower(texto[:4000])
    if "manifestacao em julgamento de recurso" in a:
        return "manifestacao_autoridade"
    if ("resposta ao recurso" in a or "julgamento recurso administrativo" in a) and "recorrent" in a:
        return "recurso"
    if re.search(r"relatorio( final)? n", a) and "exequibilidade" in a:
        return "exequibilidade"
    if "parecer tecnico" in a and re.search(r"^\s*(?:[a-z]\)\s*)?empresa:", a, re.M) and "solicitacao de parecer" not in a:
        return "parecer_tecnico"
    return None


EXTRATORES = {"exequibilidade": extrair_relatorio, "recurso": extrair_recurso,
              "manifestacao_autoridade": extrair_manifestacao, "parecer_tecnico": extrair_parecer}


def anexar_tr(reg: dict, tr: dict[int, dict]) -> None:
    reg["itens_tr"] = [{"item": f"{i:03d}", **{k: tr[i][k] for k in
                        ("lote_titulo", "codigo", "catalogo", "especificacao", "quantidade", "unidade", "valor_unitario")}}
                       for i in reg.get("itens") or [] if i in tr]
    reg["itens"] = [f"{i:03d}" for i in reg.get("itens") or []]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Decisões (exequibilidade, recurso) de um pregão SISLOG em JSONL")
    ap.add_argument("--pasta", required=True, type=Path, help="pasta com os PDFs (ou .txt) do processo")
    ap.add_argument("--processo", required=True, help="idLicitacao do SISLOG")
    ap.add_argument("--saida", required=True, type=Path)
    ap.add_argument("--tr", type=Path, help="Termo de Referência (padrão: arquivo com 'TERMO DE REFER' no nome)")
    ap.add_argument("--chat", type=Path, help="saída do rotular_chat.py: data de publicação de pareceres sem data")
    a = ap.parse_args(argv)

    arquivos = sorted(p for p in a.pasta.rglob("*") if p.suffix.lower() in (".pdf", ".txt", ".html") and p.is_file()
                      and p.name != "pagina.html")
    tr_arq = a.tr or next((p for p in arquivos if re.search(r"termo.de.refer", ascii_lower(p.name))), None)
    if not tr_arq:
        sys.exit("Termo de Referência não encontrado: passe --tr.")
    tr = carregar_tr(ler(tr_arq))
    chat = [json.loads(x) for x in a.chat.read_text(encoding="utf-8").splitlines() if x.strip()] if a.chat else []
    lotes_tr = {d["lote"] for d in tr.values()} - {None}
    print(f"TR: {tr_arq.name} -> {len(tr)} itens" + (f" em {len(lotes_tr)} lotes" if lotes_tr else " (disputa por item)"))

    a.saida.parent.mkdir(parents=True, exist_ok=True)
    tipos: Counter[str] = Counter()
    decisoes: Counter[str] = Counter()
    vistos: set[str] = set()
    n = 0
    with a.saida.open("w", encoding="utf-8") as f:
        for arq in arquivos:
            try:
                texto = ler(arq)
            except Exception as e:  # PDF imagem/corrompido: segue
                print(f"  ⚠ {arq.name}: {e}")
                continue
            tipo = tipo_documento(texto)
            if not tipo:
                continue
            chave = sei(texto) or junta(texto)[:500]
            if chave in vistos:  # mesmo documento baixado duas vezes
                print(f"  ↺ duplicado: {arq.name}")
                continue
            vistos.add(chave)
            for k, reg in enumerate(EXTRATORES[tipo](texto, tr), 1):
                n += 1
                datar_pelo_chat(reg, chat)
                anexar_tr(reg, tr)
                linha = {"id": f"sislog-{a.processo}-{tipo}-{n:03d}", "tipo": tipo, "processo": str(a.processo),
                         "fonte_url": URL_PROCESSO.format(a.processo), "documento": arq.name,
                         "sei": sei(texto), "versao": VERSAO, **reg}
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
                tipos[tipo] += 1
                decisoes[f"{tipo}:{reg.get('decisao')}"] += 1
                for al in reg.get("alertas") or []:
                    print(f"  ⚠ {reg.get('empresa')} item {','.join(reg['itens'])}: {al}")

    print(f"✅ {n} registros -> {a.saida}")
    print("   por tipo:", dict(tipos))
    for k, v in sorted(decisoes.items()):
        print(f"   {v:4d}  {k}")


if __name__ == "__main__":
    main()
