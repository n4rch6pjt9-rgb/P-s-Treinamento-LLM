"""Rótulo por regra das mensagens do chat de um processo do SISLOG (Goiás), a partir do HTML público.

Entrada: o HTML da página pública do processo, salvo do navegador ou baixado sem login:
  https://sislog.go.gov.br/PanelAquisicao/DetalhesLicitacao?idLicitacao=<numero>

Saída: um JSONL com uma linha por mensagem. Mensagem com texto fixo do sistema recebe rótulo por regra
(determinístico, sem LLM). As demais saem com status "pendente_llm" para a etapa de extração com LLM e revisão.

Nada é inventado: campo que a regra não encontra sai null. O autor só é afirmado quando o texto é
mensagem automática do sistema ou traz fórmula explícita do pregoeiro; o resto fica "indeterminado".

Uso:
  python training/rotular_chat.py --html caminho/pagina.html --processo 114655 \
      --saida training/data/chat_114655.jsonl
"""
from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

FUSO_BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019
URL_PROCESSO = "https://sislog.go.gov.br/PanelAquisicao/DetalhesLicitacao?idLicitacao={}"
VERSAO_REGRAS = "2026-10-15"


class _TabelaMensagens(HTMLParser):
    """Lê as linhas (data/hora, mensagem) da tabela que vem logo depois da legenda "Mensagens"."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._na_legenda = False
        self._depois_da_legenda = False
        self._na_tabela = False
        self._profundidade_tabela = 0
        self._na_celula = False
        self._celulas: list[str] = []
        self._buffer: list[str] = []
        self.linhas: list[tuple[str, str]] = []
        self._terminou = False

    def handle_starttag(self, tag, attrs):
        if self._terminou:
            return
        if tag == "legend":
            self._na_legenda = True
            self._buffer = []
        elif tag == "table" and self._depois_da_legenda:
            self._profundidade_tabela += 1
            self._na_tabela = True
        elif tag == "tr" and self._na_tabela:
            self._celulas = []
        elif tag == "td" and self._na_tabela:
            self._na_celula = True
            self._buffer = []
        elif tag == "br" and self._na_celula:
            self._buffer.append("\n")

    def handle_endtag(self, tag):
        if self._terminou:
            return
        if tag == "legend" and self._na_legenda:
            self._na_legenda = False
            if "".join(self._buffer).strip() == "Mensagens":
                self._depois_da_legenda = True
        elif tag == "td" and self._na_celula:
            self._na_celula = False
            self._celulas.append("".join(self._buffer).strip())
        elif tag == "tr" and self._na_tabela and len(self._celulas) == 2:
            data, texto = self._celulas
            if re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}", data):
                self.linhas.append((data, texto))
        elif tag == "table" and self._na_tabela:
            self._profundidade_tabela -= 1
            if self._profundidade_tabela == 0:
                self._na_tabela = False
                self._terminou = True

    def handle_data(self, data):
        if self._na_legenda or self._na_celula:
            self._buffer.append(data)


# Regras na ordem de prioridade: a primeira que casa define o rótulo. Todas são mensagens de texto fixo.
# (rótulo, autor, padrão)
REGRAS: list[tuple[str, str, re.Pattern[str]]] = [
    ("diligencia_liberada", "sistema", re.compile(r"^\(Mensagem Automática\).*liberou diligência")),
    ("habilitacao", "sistema", re.compile(r"^\(Mensagem Automática\).*habilitou a documentação")),
    ("mensagem_automatica", "sistema", re.compile(r"^\(Mensagem Automática\)")),
    ("proposta_excluida", "sistema", re.compile(r"^A proposta de valor R\$ [\d.,]+ do lote .* foi excluid", re.S)),
    ("lance_exclusao_solicitada", "sistema", re.compile(r"foi solicitado exclusão pelo Fornecedor")),
    ("fechamento_aviso", "sistema", re.compile(r"avisamos que em 5\(cinco\) minutos será iniciado o fechamento")),
    ("fechamento_inicio", "sistema", re.compile(r"foi iniciado o Fechamento com Prorrogação Automática")),
    ("desempate_inicio", "sistema", re.compile(r"disputa para empat\w+ para o lote")),
    ("liberado_julgamento", "sistema", re.compile(r"^O Pregoeiro liberou para julgamento o lote")),
    ("negociacao_convite", "sistema", re.compile(r"^O Pregoeiro convida o Fornecedor que efetuou o lance")),
    ("negociacao_lance", "sistema", re.compile(r"^O Fornecedor enviou o lance de negociação")),
    ("desclassificacao", "sistema", re.compile(r"^O Fornecedor que efetuou o lance de [\d.,]+ para o Lote .* foi Desclassificado")),
    ("habilitacao", "sistema", re.compile(r"^O Fornecedor que efetuou o lance de [\d.,]+ para o Lote .* foi Habilitado")),
    ("fase_lances_reestabelecida", "sistema", re.compile(r"foi reestabelecido a fase de lances para o lote")),
    ("vencedor_declarado", "sistema", re.compile(r"declaro vencedor do lote")),
    ("lote_fracassado", "sistema", re.compile(r"declaro fracassado o lote")),
    ("lote_deserto", "sistema", re.compile(r"declaro deserto o lote")),
    ("declaracao_removida", "sistema", re.compile(r"^O Pregoeiro removeu a declaração de vencedor/fracassado")),
    ("intencao_recurso", "sistema", re.compile(r"^O Fornecedor Manifestou a intenção de recurso")),
    ("adjudicacao", "sistema", re.compile(r"foi julgado como adjudicado pelo pregoeiro")),
    ("sessao_encerrada", "sistema", re.compile(r"^A sessão está encerrada")),
    ("sessao_suspensa", "pregoeiro", re.compile(r"^A sessão está suspensa", re.I)),
    ("sessao_retomada", "pregoeiro", re.compile(r"Retomamos a sessão|Etapa de Lances será restabelecida", re.I)),
    # Fórmulas do pregoeiro (texto livre, mas com abertura fixa)
    ("convocacao_proposta", "pregoeiro", re.compile(r"Convocamos a empresa .* a encaminhar")),
    ("convocacao_ajuste", "pregoeiro", re.compile(r"Convocamos a empresa")),
    # Parecer da equipe de apoio, item a item: o rótulo é seguro, o motivo ainda precisa de extração (LLM)
    ("parecer_item_tr", "pregoeiro", re.compile(r"^\d\)\s*Ite(?:m|ns) .* do Termo de Referência", re.S)),
    ("decisao_recurso", "pregoeiro", re.compile(r"Diante do exposto, decide-se")),
    ("inabilitacao", "pregoeiro", re.compile(r"foi inabilitada, por")),
    ("parecer_publicado", "pregoeiro", re.compile(r"Foi dad[ao] (a )?publicidade (ao Parecer|da decisão)", re.I)),
    ("documentos_publicados", "pregoeiro", re.compile(r"(será|foi) dad[oa] (a )?Publicidade de toda a documentação", re.I)),
    ("documentos_recebidos", "pregoeiro", re.compile(r"encaminhou a (cópia da Proposta|documentação)")),
    ("em_analise", "pregoeiro", re.compile(r"(encontram-se|ainda se encontram?) (ainda )?em análise")),
    ("cadfor", "pregoeiro", re.compile(r"Cadastro de Fornecedores do Estado - CADFOR")),
    ("alerta_inexequibilidade", "pregoeiro", re.compile(r"item 7\.11 do Edital, que trata sobre a Inexequibilidade")),
    ("negociacao_pedido_ajuste", "pregoeiro", re.compile(r"ajuste dos valores unitários|ABA \"?NEGOCIAÇÃO\"?", re.I)),
    # 15/10/2026: fórmulas de outros pregoeiros do SISLOG (caso 104744, SEEL 2024). Regras amplas, depois das fixas.
    ("help_desk", "sistema", re.compile(r"^Em atendimento ao (Help Desk|HD)\s*\d+", re.I)),
    ("pedido_cancelamento_lance", "fornecedor",
     re.compile(r"(cancelamento|exclus[ãa]o|cancelar|excluir) (d[oe] )?(nosso |meu )?lance|cota[çc][ãa]o errada|cotamos (a quantidade|o valor) errad", re.I)),
    ("instabilidade_sistema", None,
     re.compile(r"sistema (est[áa] |ficou )?(inst[áa]vel|oscilando|travando|caiu|fora do ar)|toda hora desconect|instabilidade|"
                r"est[áa]vel para n[óo]s|n[ãa]o houve oscila[çc][ãa]o|problema da sua conex[ãa]o", re.I)),
    ("diligencia_aba", "pregoeiro", re.compile(r"aba (de |\")?dilig[êe]ncias?|objeto de dilig[êe]ncia|empresas diligenciadas", re.I)),
    ("resultado_analise_tecnica", "pregoeiro",
     re.compile(r"detentora d[ae]s? melhor(es)? ofertas?.{0,120}\bfoi (aprovad|reprovad|desclassificad|habilitad)|relat[óo]rio (de an[áa]lise )?t[ée]cnic", re.I | re.S)),
    ("parecer_publicado", "pregoeiro", re.compile(r"(parecer|julgamentos? dos recursos|documentos).{0,60}(dispon[íi]ve(l|is)|p[úu]blicos?|tornad[oa]s p[úu]blic)", re.I)),
    ("declaracao_vencedor_aviso", "pregoeiro", re.compile(r"declar(ar|aremos|a[çc][ãa]o de) (as empresas )?vencedor|ser[áa] declarado vencedor|declarados vencedores", re.I)),
    ("recurso_aviso", "pregoeiro", re.compile(r"\b(prazo|fase|aba|manifesta[çc][ãa]o) (de |para )?(recurso|recursal)|contrarraz", re.I)),
    ("desclassificacao_aviso", "pregoeiro", re.compile(r"\b(iremos|irei|vamos) (proceder [àa] )?desclassifica|ser[ãa]o desclassificad", re.I)),
    ("convocacao_remanescente", "pregoeiro", re.compile(r"remanescentes?", re.I)),
    ("cadfor", "pregoeiro", re.compile(r"\bCADFOR\b")),
    ("alerta_inexequibilidade", "pregoeiro", re.compile(r"inexequ[íi]ve(l|is)|exequibilidade", re.I)),
    ("negociacao_orientacao", "pregoeiro", re.compile(r"negocia[çc][ãa]o", re.I)),
    ("orientacao_lances", "pregoeiro", re.compile(r"valor(es)? (total do lote|estimados)|lances deverão ser dados", re.I)),
    ("sessao_suspensa", "pregoeiro", re.compile(r"sess[ãa]o (ficar[áa] |ser[áa] |est[áa] )?suspensa|retorno (estava )?marcado|daremos in[íi]cio", re.I)),
    ("saudacao", None, re.compile(r"^(boa (tarde|noite)|bom dia|ol[áa])[!,. a-z]{0,25}$|^(ok|perfeito|obrigad[oa]|grat[oa]|aqui|sim)[!. ]{0,3}$", re.I)),
]

# Rótulo seguro por regra, mas o conteúdo (motivo, exigência) ainda precisa de extração com LLM e revisão
EXTRAIR_COM_LLM = {"parecer_item_tr", "decisao_recurso"}

RE_LOTE = re.compile(r"\(?Lote:?\s*0?(\d{1,3})\b", re.I)
RE_LOTES_PARA = re.compile(r"^\s*PARA (?:O|OS|AS)? ?LOTES?\b([^:]{1,80}):", re.I)
RE_VALOR = re.compile(r"(?:R\$\s*|lance (?:de )?(?:valor )?(?:R\$\s*)?|no valor de:\s*)([\d]{1,3}(?:\.\d{3})*,\d{2})")
RE_EMPRESA = re.compile(r"(?:a empresa|da empresa|pela empresa)\s+([A-ZÀ-Ú0-9&][A-ZÀ-Ú0-9&.,\- ]{3,90}?)(?=,|\s+(?:a encaminhar|foi|encaminhou|foram|por)\b)")
RE_ITENS_TR = re.compile(r"Ite(?:m|ns)\s+([\d.;,\se]+?)\s+do Termo de Referência", re.I)
RE_PRAZO_HORAS = re.compile(r"no prazo de (\d{1,3}) ?horas", re.I)
RE_MOTIVO_INAB = re.compile(r"foi inabilitada, por (.{10,})", re.S)
# Fim de frase: ponto seguido de maiúscula, exceto depois de abreviação comum em texto jurídico (art., inc., nº., Lei)
RE_FIM_FRASE = re.compile(r"(?<!\bart)(?<!\barts)(?<!\binc)(?<!\bn)(?<!\bnº)(?<!\bp)\.\s+(?=[A-ZÀ-Ú])")
RE_ITENS_EDITAL = re.compile(r"ite(?:m|ns) ([\d.]+(?:,? (?:e )?[\d.]+)*) do edital", re.I)


def _ate_fim_da_frase(trecho: str) -> str:
    fim = RE_FIM_FRASE.search(trecho)
    return (trecho[:fim.start()] if fim else trecho).strip().rstrip(".")


def _lotes(texto: str) -> list[int]:
    m = RE_LOTES_PARA.search(texto)
    if m:
        return sorted({int(n) for n in re.findall(r"\d+", m.group(1))})
    return sorted({int(n) for n in RE_LOTE.findall(texto)})


def _valor(texto: str) -> float | None:
    m = RE_VALOR.search(texto)
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def _itens(texto: str, padrao: re.Pattern[str]) -> list[str]:
    itens: list[str] = []
    for grupo in padrao.findall(texto):
        itens += [i.strip(" .") for i in re.split(r"[;,]|\se\s", grupo) if re.search(r"\d", i)]
    return itens


def rotular(data_hora: str, texto: str) -> dict:
    rotulo = autor = regra = None
    for nome, quem, padrao in REGRAS:
        if padrao.search(texto):
            rotulo, autor, regra = nome, quem, padrao.pattern
            break
    autor_por = "regra" if autor else None
    if re.match(r"^\(Fornecedor\):", texto):
        autor, autor_por = "fornecedor", "texto"
    if autor is None and re.match(r"^(Prezad|Sr\.? ?Pregoeiro|Senhor Pregoeiro|Boa (tarde|noite)|Bom dia)", texto, re.I) \
            and re.search(r"pregoeiro", texto, re.I):
        autor, autor_por = "fornecedor", "heuristica"  # dirige-se ao pregoeiro

    local = datetime.strptime(data_hora, "%d/%m/%Y %H:%M:%S").replace(tzinfo=FUSO_BRASILIA)
    motivo = RE_MOTIVO_INAB.search(texto)
    prazo = RE_PRAZO_HORAS.search(texto)
    empresa = RE_EMPRESA.search(texto)
    return {
        "data_hora_brasilia": local.isoformat(),
        "data_hora_utc": local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "texto": texto,
        "autor": autor or "indeterminado",
        "autor_por": autor_por,
        "rotulo": rotulo,
        "rotulo_regra": regra,
        "status": ("regra_extrair" if rotulo in EXTRAIR_COM_LLM else "regra") if rotulo else "pendente_llm",
        "lotes": _lotes(texto),
        "empresa": empresa.group(1).strip(" ,.") if empresa else None,
        "valor": _valor(texto),
        "prazo_horas": int(prazo.group(1)) if prazo else None,
        "motivo_inabilitacao": _ate_fim_da_frase(motivo.group(1)) if motivo else None,
        "itens_tr": _itens(texto, RE_ITENS_TR),
        "itens_edital": _itens(texto, RE_ITENS_EDITAL),
    }


def _chave_ata(data_hora_iso: str, texto: str) -> tuple[str, str]:
    t = unicodedata.normalize("NFKD", re.sub(r"\s+", " ", texto)).encode("ascii", "ignore").decode().lower()
    return data_hora_iso[:16], t[:40]


# Autor como a ata do SISLOG escreve -> autor do rótulo
AUTOR_ATA = {"Fornecedor": "fornecedor", "Agente de Contratação": "pregoeiro", "Pregoeiro": "pregoeiro"}


def carregar_autores_ata(caminho: Path) -> dict[tuple[str, str], str | None]:
    ata = json.loads(caminho.read_text(encoding="utf-8"))
    return {_chave_ata(m["em"], m["texto"]): m.get("autor") for m in ata.get("mensagens", [])}


def aplicar_autor_ata(linha: dict, autores: dict) -> None:
    """A ata identifica quem escreveu. Mensagem automática (rótulo de sistema) continua 'sistema': na ata ela aparece
    em nome do agente, mas é o sistema que gera. Sem par na ata, fica o que a regra decidiu."""
    if not autores:
        return
    chave = _chave_ata(linha["data_hora_brasilia"], linha["texto"])
    if chave not in autores:
        linha["autor_ata"] = None
        return
    bruto = autores[chave]
    linha["autor_ata"] = bruto
    if linha["autor_por"] == "regra" and linha["autor"] == "sistema":
        return
    if linha["autor_por"] == "texto":
        return
    if bruto is None:  # a ata não atribui autor: mensagem automática
        linha["autor"], linha["autor_por"] = "sistema", "ata"
    elif bruto in AUTOR_ATA:
        esperado = linha["autor"] if linha["autor_por"] == "regra" else None
        linha["autor"], linha["autor_por"] = AUTOR_ATA[bruto], "ata"
        # A regra supunha um autor e a ata mostra o outro lado (ex.: fornecedor perguntando sobre negociação caiu
        # em 'negociacao_orientacao' do pregoeiro). O rótulo não vale: volta para o LLM, guardando o descartado.
        partes = {"pregoeiro", "fornecedor"}
        if esperado in partes and linha["autor"] in partes and esperado != linha["autor"]:
            linha["rotulo_descartado"] = linha["rotulo"]
            linha["rotulo"] = linha["rotulo_regra"] = None
            linha["status"] = "pendente_llm"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Rótulo por regra do chat de um processo SISLOG")
    ap.add_argument("--html", required=True, type=Path, help="HTML da página pública do processo")
    ap.add_argument("--processo", required=True, help="número da contratação no SISLOG (idLicitacao)")
    ap.add_argument("--saida", required=True, type=Path)
    ap.add_argument("--ata", type=Path, help="JSON do extrair_ata_sislog.py do mesmo processo: dá o autor das mensagens")
    a = ap.parse_args(argv)
    autor_ata = carregar_autores_ata(a.ata) if a.ata else {}

    bruto = a.html.read_text(encoding="utf-8", errors="replace")
    leitor = _TabelaMensagens()
    leitor.feed(bruto)
    if not leitor.linhas:
        sys.exit("Nenhuma mensagem encontrada: confira se o HTML é a página DetalhesLicitacao do SISLOG.")

    a.saida.parent.mkdir(parents=True, exist_ok=True)
    rotulos: Counter[str] = Counter()
    autores: Counter[str] = Counter()
    status: Counter[str] = Counter()
    with a.saida.open("w", encoding="utf-8") as f:
        for seq, (data_hora, texto) in enumerate(leitor.linhas, start=1):
            linha = {
                "id": f"sislog-{a.processo}-{seq:05d}",
                "origem": "sislog",
                "processo": str(a.processo),
                "seq": seq,
                "fonte_url": URL_PROCESSO.format(a.processo),
                "versao_regras": VERSAO_REGRAS,
                **rotular(data_hora, html.unescape(texto)),
            }
            aplicar_autor_ata(linha, autor_ata)
            rotulos[linha["rotulo"] or "pendente_llm"] += 1
            autores[linha["autor"]] += 1
            status[linha["status"]] += 1
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    total = sum(rotulos.values())
    print(f"✅ {total} mensagens -> {a.saida}")
    print(f"   por regra: {total - rotulos['pendente_llm']} | pendente_llm: {rotulos['pendente_llm']}")
    print("   autores:", dict(autores))
    for nome, n in rotulos.most_common():
        print(f"   {n:5d}  {nome}")
    print("   status:", dict(status))


if __name__ == "__main__":
    main()
