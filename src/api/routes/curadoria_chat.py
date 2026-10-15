"""Curadoria humana do chat e das decisões coletadas nos portais (SISLOG, BLL, Portal de Compras Públicas).

Lê (somente leitura, o que os scripts de coleta/extração gravaram):
  training/data/{sislog,bll,pcp}/<processo>/chat.jsonl      mensagens (rotular_chat.py / extrair_ata_bll.py / coletar_pcp.py)
  training/data/sislog/<processo>/decisoes.jsonl            decisões (extrair_decisoes_sislog.py)
Escreve (só aqui; a última revisão de cada id vale):
  training/data/curadoria/gabarito_chat.jsonl
  training/data/curadoria/gabarito_decisoes.jsonl

Fila do chat: mensagens que a regra não resolveu (status pendente_llm) e, nos portais sem regra ainda (BLL, PCP),
as mensagens de pregoeiro e fornecedor. A mensagem do sistema já é rotulada por regra e não entra.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/curadoria-chat", tags=["curadoria-chat"])

RAIZ = Path(__file__).resolve().parents[3]
DADOS = RAIZ / "training" / "data"
SAIDA = DADOS / "curadoria"
PORTAIS = ("sislog", "bll", "pcp")
VERSAO_TAXONOMIA = "2026-10-15"

# Intenção da mensagem: taxonomia curta para revisão humana (os 55 rótulos de regra continuam no rotulo_regra).
INTENCOES = [
    {"id": "pergunta_fornecedor", "nome": "Pergunta / dúvida do fornecedor", "dica": "esclarecimento, como anexar, prazo de quê"},
    {"id": "pedido_prazo", "nome": "Pedido de prazo", "dica": "dilação para proposta, catálogo, documentos"},
    {"id": "desistencia_cancelamento", "nome": "Cancelamento de lance / desistência", "dica": "lance errado, pede desclassificação"},
    {"id": "negociacao_valor", "nome": "Negociação de valor", "dica": "contraproposta, 'já estamos no mínimo'"},
    {"id": "envio_documentos", "nome": "Envio de documentos", "dica": "'anexado', proposta readequada enviada"},
    {"id": "contestacao_concorrente", "nome": "Contestação de concorrente", "dica": "pede verificação/inabilitação de outra empresa"},
    {"id": "argumento_recurso", "nome": "Argumento de recurso", "dica": "razões, contrarrazões, intenção motivada"},
    {"id": "instrucao_pregoeiro", "nome": "Instrução / convocação do pregoeiro", "dica": "orienta, convoca, cobra documento"},
    {"id": "decisao_pregoeiro", "nome": "Decisão do pregoeiro", "dica": "aceita, recusa, desclassifica com motivo"},
    {"id": "agenda_sessao", "nome": "Agenda da sessão", "dica": "suspende, retoma, marca nova data"},
    {"id": "problema_sistema", "nome": "Problema no sistema", "dica": "instabilidade, help desk, erro do portal"},
    {"id": "cortesia", "nome": "Cortesia", "dica": "bom dia, obrigado, ok"},
    {"id": "outro", "nome": "Outro", "dica": "use a observação"},
]
MARCAS = [
    {"id": "erro_fornecedor", "nome": "Erro do fornecedor"},
    {"id": "erro_administracao", "nome": "Erro da administração"},
    {"id": "questao_legal", "nome": "Questão legal (Jurídico)"},
    {"id": "exemplo_ouro", "nome": "Exemplo ouro para treino"},
]
DECISOES = ["deferido", "indeferido", "aprovado", "aprovado_condicional", "reprovado", "reprovado_parcial",
            "sem_razoes", "nao_e_decisao"]
MOTIVOS = ["valor_inexequivel", "certificacao_ausente", "especificacao_divergente", "marca_modelo_ausente",
           "documento_orgao_errado", "documentacao_habilitacao", "prazo_perdido", "formalismo_excessivo",
           "requisito_opcional_exigido", "sem_razoes_recursais", "outro"]

_lock = threading.Lock()
_cache: dict = {}


def _ler_jsonl(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _arquivos(nome: str) -> list[tuple[str, str, Path]]:
    saida = []
    for portal in PORTAIS:
        base = DADOS / portal
        if base.exists():
            for p in sorted(base.glob(f"*/{nome}")):
                saida.append((portal, p.parent.name, p))
    return saida


def _assinatura(arqs: list[tuple[str, str, Path]]) -> tuple:
    return tuple((str(p), p.stat().st_mtime) for _, _, p in arqs)


def _chat() -> dict:
    """{processo_chave: [mensagens em ordem]} com cache por mtime."""
    arqs = _arquivos("chat.jsonl")
    sig = _assinatura(arqs)
    if _cache.get("chat_sig") != sig:
        por_proc = {}
        for portal, proc, p in arqs:
            msgs = _ler_jsonl(p)
            for m in msgs:
                m["_portal"], m["_processo"] = portal, proc
            por_proc[f"{portal}:{proc}"] = msgs
        _cache["chat"], _cache["chat_sig"] = por_proc, sig
    return _cache["chat"]


def _decisoes() -> list[dict]:
    arqs = _arquivos("decisoes.jsonl")
    sig = _assinatura(arqs)
    if _cache.get("dec_sig") != sig:
        todas = []
        for portal, proc, p in arqs:
            for d in _ler_jsonl(p):
                d["_portal"], d["_processo"] = portal, proc
                todas.append(d)
        _cache["dec"], _cache["dec_sig"] = todas, sig
    return _cache["dec"]


def _gabarito(nome: str) -> dict:
    p = SAIDA / nome
    if not p.exists():
        return {}
    mt = p.stat().st_mtime
    if _cache.get(f"{nome}_mt") != mt:
        g = {}
        for r in _ler_jsonl(p):
            g[r["id"]] = r  # a última revisão vale
        _cache[nome], _cache[f"{nome}_mt"] = g, mt
    return _cache[nome]


def _entra_na_fila(m: dict) -> bool:
    if m.get("autor") == "sistema":
        return False
    if "status" in m:  # SISLOG: só o que a regra não resolveu
        return m["status"] == "pendente_llm"
    return m.get("autor") in ("fornecedor", "pregoeiro", "indeterminado")  # BLL/PCP: ainda sem regras


def _resumo_msg(m: dict) -> dict:
    return {"id": m["id"], "data_hora": m.get("data_hora_brasilia"), "autor": m.get("autor"),
            "empresa": m.get("empresa"), "rotulo_regra": m.get("rotulo"), "texto": m.get("texto", "")}


@router.get("/taxonomia")
def taxonomia():
    return {"versao": VERSAO_TAXONOMIA, "intencoes": INTENCOES, "marcas": MARCAS, "decisoes": DECISOES,
            "motivos": MOTIVOS}


@router.get("/stats")
def stats():
    chat, gab = _chat(), _gabarito("gabarito_chat.jsonl")
    por_portal: dict = {}
    for chave, msgs in chat.items():
        portal = chave.split(":")[0]
        s = por_portal.setdefault(portal, {"processos": 0, "mensagens": 0, "na_fila": 0, "revisadas": 0})
        s["processos"] += 1
        s["mensagens"] += len(msgs)
        for m in msgs:
            if _entra_na_fila(m):
                s["na_fila"] += 1
                if m["id"] in gab:
                    s["revisadas"] += 1
    dec, gdec = _decisoes(), _gabarito("gabarito_decisoes.jsonl")
    return {"por_portal": por_portal, "decisoes": len(dec), "decisoes_revisadas": sum(1 for d in dec if d["id"] in gdec),
            "processos": sorted(chat.keys())}


@router.get("/fila")
def fila(offset: int = 0, limite: int = 20, portal: str = "", processo: str = "", autor: str = "",
         incluir_revisadas: bool = False, contexto: int = 3):
    chat, gab = _chat(), _gabarito("gabarito_chat.jsonl")
    itens = []
    for chave, msgs in chat.items():
        p, proc = chave.split(":", 1)
        if (portal and p != portal) or (processo and proc != processo):
            continue
        for i, m in enumerate(msgs):
            if not _entra_na_fila(m) or (autor and m.get("autor") != autor):
                continue
            if m["id"] in gab and not incluir_revisadas:
                continue
            itens.append({**_resumo_msg(m), "portal": p, "processo": proc,
                          "lotes": m.get("lotes") or [], "revisao": gab.get(m["id"]),
                          "antes": [_resumo_msg(x) for x in msgs[max(0, i - contexto): i]],
                          "depois": [_resumo_msg(x) for x in msgs[i + 1: i + 1 + max(0, contexto - 1)]]})
    # fornecedor primeiro: é o lado que mais falta no treino
    itens.sort(key=lambda x: (x["autor"] != "fornecedor", x["portal"], x["processo"], x["data_hora"] or ""))
    return {"total": len(itens), "offset": offset, "itens": itens[offset: offset + limite]}


@router.get("/decisoes")
def decisoes(offset: int = 0, limite: int = 10, incluir_revisadas: bool = False):
    dec, gab = _decisoes(), _gabarito("gabarito_decisoes.jsonl")
    lista = [d for d in dec if incluir_revisadas or d["id"] not in gab]
    lista.sort(key=lambda d: (d.get("status") != "pendente_llm", d["_processo"], d["id"]))
    out = []
    for d in lista[offset: offset + limite]:
        texto = d.get("texto") or d.get("motivo") or d.get("fundamentacao") or ""
        out.append({"id": d["id"], "portal": d["_portal"], "processo": d["_processo"], "tipo": d.get("tipo"),
                    "subtipo": d.get("subtipo"), "documento": d.get("documento"), "lote": d.get("lote"),
                    "lotes": d.get("lotes"), "empresa": d.get("empresa") or d.get("licitante") or d.get("recorrida"),
                    "recorrente": d.get("recorrente"), "decisao_regra": d.get("decisao"),
                    "categorias_regra": d.get("categorias") or [], "ementa": d.get("ementa"),
                    "alertas": d.get("alertas") or [], "texto": texto[:20000], "revisao": gab.get(d["id"])})
    return {"total": len(lista), "offset": offset, "itens": out}


class RevisaoChat(BaseModel):
    id: str
    intencao: str
    marcas: list[str] = Field(default_factory=list)
    autor_corrigido: str | None = None
    obs: str = ""


class LoteChat(BaseModel):
    revisado_por: str
    revisoes: list[RevisaoChat]


class RevisaoDecisao(BaseModel):
    id: str
    decisao: str
    motivos: list[str] = Field(default_factory=list)
    marcas: list[str] = Field(default_factory=list)
    obs: str = ""


class LoteDecisao(BaseModel):
    revisado_por: str
    revisoes: list[RevisaoDecisao]


def _anexar(nome: str, linhas: list[dict]) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    with _lock, open(SAIDA / nome, "a", encoding="utf-8") as f:
        for l in linhas:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")


@router.post("/revisar")
def revisar(lote: LoteChat):
    if not lote.revisado_por.strip():
        raise HTTPException(422, "informe revisado_por")
    validas = {i["id"] for i in INTENCOES}
    marcas = {m["id"] for m in MARCAS}
    idx = {m["id"]: m for msgs in _chat().values() for m in msgs}
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    linhas = []
    for r in lote.revisoes:
        if r.intencao not in validas or not set(r.marcas) <= marcas:
            raise HTTPException(422, f"rótulo inválido em {r.id}")
        m = idx.get(r.id)
        if m is None:
            raise HTTPException(404, f"mensagem não encontrada: {r.id}")
        linhas.append({"id": r.id, "portal": m["_portal"], "processo": m["_processo"],
                       "data_hora": m.get("data_hora_brasilia"), "autor": r.autor_corrigido or m.get("autor"),
                       "empresa": m.get("empresa"), "texto": m.get("texto"), "rotulo_regra": m.get("rotulo"),
                       "intencao": r.intencao, "marcas": r.marcas, "obs": r.obs,
                       "revisado_por": lote.revisado_por.strip(), "revisado_em": agora,
                       "taxonomia": VERSAO_TAXONOMIA})
    _anexar("gabarito_chat.jsonl", linhas)
    return {"gravadas": len(linhas)}


@router.post("/revisar-decisao")
def revisar_decisao(lote: LoteDecisao):
    if not lote.revisado_por.strip():
        raise HTTPException(422, "informe revisado_por")
    idx = {d["id"]: d for d in _decisoes()}
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    linhas = []
    for r in lote.revisoes:
        if r.decisao not in DECISOES or not set(r.motivos) <= set(MOTIVOS):
            raise HTTPException(422, f"rótulo inválido em {r.id}")
        d = idx.get(r.id)
        if d is None:
            raise HTTPException(404, f"decisão não encontrada: {r.id}")
        linhas.append({"id": r.id, "portal": d["_portal"], "processo": d["_processo"], "tipo": d.get("tipo"),
                       "subtipo": d.get("subtipo"), "documento": d.get("documento"),
                       "decisao_regra": d.get("decisao"), "decisao": r.decisao, "motivos": r.motivos,
                       "marcas": r.marcas, "obs": r.obs, "revisado_por": lote.revisado_por.strip(),
                       "revisado_em": agora, "taxonomia": VERSAO_TAXONOMIA})
    _anexar("gabarito_decisoes.jsonl", linhas)
    return {"gravadas": len(linhas)}
