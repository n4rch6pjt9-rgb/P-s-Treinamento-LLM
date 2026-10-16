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

# Taxonomia (intenções, temas, sinais e migração de versões antigas) vem de um arquivo só, o mesmo que o export do
# Tunix lê: training/config/taxonomia_chat.json. Os rótulos de regra continuam no rotulo_regra de cada mensagem.
_TAX = json.loads((RAIZ / "training" / "config" / "taxonomia_chat.json").read_text(encoding="utf-8"))
VERSAO_TAXONOMIA = _TAX["versao"]
INTENCOES = _TAX["intencoes"]
TEMAS = _TAX["temas"]
SINAIS = _TAX["sinais"]
MARCAS = SINAIS  # nome antigo: a aba de decisões e as revisões de 2026-10-15 gravaram os sinais como "marcas"
_IDS_INTENCAO = {i["id"] for i in INTENCOES}


def intencao_vigente(rev: dict | None) -> str | None:
    """Intenção da revisão na taxonomia atual. None = precisa revisar de novo (categoria foi dividida)."""
    if not rev:
        return None
    versao, intencao = rev.get("taxonomia"), rev.get("intencao")
    if versao != VERSAO_TAXONOMIA:
        mapa = _TAX.get("migracao", {}).get(versao, {})
        if intencao in mapa:
            intencao = mapa[intencao]
    return intencao if intencao in _IDS_INTENCAO else None
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


def _sugestoes() -> dict:
    """Sugestões do Claude (training/rotular_claude.py), só da taxonomia atual; a mais recente de cada id vale."""
    p = SAIDA / "sugestoes_chat.jsonl"
    if not p.exists():
        return {}
    mt = p.stat().st_mtime
    if _cache.get("sug_mt") != mt:
        s = {}
        for r in _ler_jsonl(p):
            if r.get("taxonomia") == VERSAO_TAXONOMIA and r.get("intencao") in _IDS_INTENCAO:
                s[r["id"]] = r
        _cache["sug"], _cache["sug_mt"] = s, mt
    return _cache["sug"]


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
    return {"versao": VERSAO_TAXONOMIA, "intencoes": INTENCOES, "temas": TEMAS, "sinais": SINAIS,
            "marcas": MARCAS, "decisoes": DECISOES, "motivos": MOTIVOS}


@router.get("/stats")
def stats():
    chat, gab, sug = _chat(), _gabarito("gabarito_chat.jsonl"), _sugestoes()
    por_portal: dict = {}
    divergentes = 0
    for chave, msgs in chat.items():
        portal = chave.split(":")[0]
        s = por_portal.setdefault(portal, {"processos": 0, "mensagens": 0, "na_fila": 0, "revisadas": 0,
                                           "a_rever": 0})
        s["processos"] += 1
        s["mensagens"] += len(msgs)
        for m in msgs:
            if m["id"] in gab and m["id"] in sug and intencao_vigente(gab[m["id"]]) not in (None, sug[m["id"]]["intencao"]):
                divergentes += 1
            if m["id"] in gab and intencao_vigente(gab[m["id"]]) is None:
                s["a_rever"] += 1  # revisada na taxonomia antiga numa categoria que foi dividida
            if _entra_na_fila(m):
                s["na_fila"] += 1
                if m["id"] in gab and intencao_vigente(gab[m["id"]]):
                    s["revisadas"] += 1
    dec, gdec = _decisoes(), _gabarito("gabarito_decisoes.jsonl")
    return {"por_portal": por_portal, "divergentes": divergentes, "decisoes": len(dec), "decisoes_revisadas": sum(1 for d in dec if d["id"] in gdec),
            "processos": sorted(chat.keys())}


@router.get("/fila")
def fila(offset: int = 0, limite: int = 20, portal: str = "", processo: str = "", autor: str = "",
         incluir_revisadas: bool = False, rever: bool = False, contexto: int = 3, ordem: str = "",
         busca: str = "", divergentes: bool = False):
    """rever=True: só as já revisadas cuja categoria foi dividida na taxonomia nova (ex.: contestação, outro).
    ordem="incerteza": primeiro as que o Claude sugeriu com confiança baixa, depois média, alta e sem sugestão."""
    chat, gab, sug = _chat(), _gabarito("gabarito_chat.jsonl"), _sugestoes()
    itens = []
    for chave, msgs in chat.items():
        p, proc = chave.split(":", 1)
        if (portal and p != portal) or (processo and proc != processo):
            continue
        for i, m in enumerate(msgs):
            rev = gab.get(m["id"])
            a_rever = rev is not None and intencao_vigente(rev) is None
            if divergentes:  # revisão humana válida que discorda da sugestão do Claude
                if rev is None or m["id"] not in sug or intencao_vigente(rev) in (None, sug[m["id"]]["intencao"]):
                    continue
            elif rever:
                if not a_rever:
                    continue
            elif not _entra_na_fila(m) or (rev is not None and not a_rever and not incluir_revisadas):
                continue
            if autor and (rev or {}).get("autor", m.get("autor")) != autor:
                continue
            if busca and busca.lower() not in (m.get("texto") or "").lower():
                continue
            itens.append({**_resumo_msg(m), "portal": p, "processo": proc,
                          "lotes": m.get("lotes") or [], "revisao": gab.get(m["id"]), "sugestao": sug.get(m["id"]),
                          "antes": [_resumo_msg(x) for x in msgs[max(0, i - contexto): i]],
                          "depois": [_resumo_msg(x) for x in msgs[i + 1: i + 1 + max(0, contexto - 1)]]})
    # fornecedor primeiro: é o lado que mais falta no treino
    itens.sort(key=lambda x: (x["autor"] != "fornecedor", x["portal"], x["processo"], x["data_hora"] or ""))
    if ordem == "incerteza":
        peso = {"baixa": 0, "media": 1, "alta": 2}
        itens.sort(key=lambda x: peso.get((x["sugestao"] or {}).get("confianca"), 3))  # estável: mantém o resto
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
    temas: list[str] = Field(default_factory=list)
    sinais: list[str] = Field(default_factory=list)
    marcas: list[str] = Field(default_factory=list)  # nome antigo de "sinais"; ainda aceito
    autor_corrigido: str | None = None
    obs: str = ""
    sugestao_intencao: str | None = None  # o que o Claude sugeriu (para medir quanto a sugestão é aceita)
    sugestao_modelo: str | None = None


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
    temas_ok = {t["id"] for t in TEMAS}
    sinais_ok = {s["id"] for s in SINAIS}
    idx = {m["id"]: m for msgs in _chat().values() for m in msgs}
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    linhas = []
    for r in lote.revisoes:
        sinais = sorted(set(r.sinais) | set(r.marcas))
        if r.intencao not in _IDS_INTENCAO or not set(r.temas) <= temas_ok or not set(sinais) <= sinais_ok:
            raise HTTPException(422, f"rótulo inválido em {r.id}")
        m = idx.get(r.id)
        if m is None:
            raise HTTPException(404, f"mensagem não encontrada: {r.id}")
        linhas.append({"id": r.id, "portal": m["_portal"], "processo": m["_processo"],
                       "data_hora": m.get("data_hora_brasilia"), "autor": r.autor_corrigido or m.get("autor"),
                       "empresa": m.get("empresa"), "texto": m.get("texto"), "rotulo_regra": m.get("rotulo"),
                       "intencao": r.intencao, "temas": r.temas, "sinais": sinais, "marcas": sinais, "obs": r.obs,
                       "sugestao_intencao": r.sugestao_intencao, "sugestao_modelo": r.sugestao_modelo,
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
