"""Definições compartilhadas do classificador de escopo LicitaGym (rótulos, prompt, resposta, split)."""
from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from typing import Iterable

# Rótulos de escopo por item (mesmo vocabulário de licitacao_itens.categoria_escopo, + manutencao e fora).
ROTULOS = ("forte", "fraco", "piso", "borracha", "obra_piso", "manutencao", "fora")
DESCRICAO_ROTULOS = {
    "forte": "equipamento de academia/ginástica/musculação (esteira, leg press, anilha, halter...)",
    "fraco": "material esportivo genérico (bola, rede, uniforme, troféu...)",
    "piso": "piso emborrachado, placa/tapete de borracha, piso SBR/EPDM, grama sintética (fornecimento)",
    "borracha": "borracha granulada/raspa/infill ou compra direta de borracha",
    "obra_piso": "obra/instalação de quadra, campo ou piso (monolítico, substituição de gramado...)",
    "manutencao": "peça de reposição de aparelho de academia (cabo de aço, polia, estofamento...)",
    "fora": "fora do escopo da Playfit",
}

INSTRUCAO = (
    "Você classifica itens de licitações públicas para a Playfit (equipamentos de academia, pisos de borracha "
    "e grama sintética). Responda só com JSON no formato {\"categoria\": \"<rótulo>\"}. Rótulos: "
    + "; ".join(f"{k} = {v}" for k, v in DESCRICAO_ROTULOS.items())
    + "."
)


def normalizar(t: str | None) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip()


def montar_prompt(descricao_item: str, objeto: str | None = None) -> str:
    partes = [INSTRUCAO]
    if objeto:
        partes.append(f"Objeto da licitação: {objeto.strip()[:600]}")
    partes.append(f"Item: {descricao_item.strip()[:600]}")
    return "\n".join(partes)


def montar_resposta(categoria: str) -> str:
    if categoria not in ROTULOS:
        raise ValueError(f"rótulo inválido: {categoria!r}")
    return json.dumps({"categoria": categoria}, ensure_ascii=False)


def ler_resposta(texto: str) -> str | None:
    """Extrai o rótulo da saída do modelo; None se não der para ler."""
    m = re.search(r"\{[^{}]*\}", texto or "")
    if m:
        try:
            cat = json.loads(m.group(0)).get("categoria")
            return cat if cat in ROTULOS else None
        except json.JSONDecodeError:
            pass
    m = re.search(r"\b(" + "|".join(ROTULOS) + r")\b", texto or "")
    return m.group(1) if m else None


def grupo_de(registro: dict) -> str:
    """Chave de agrupamento do split: itens da mesma licitação nunca ficam em conjuntos diferentes."""
    return str(registro.get("grupo") or registro.get("licitacao_id") or registro["id"])


def dividir(registros: Iterable[dict], proporcoes=(0.7, 0.15, 0.15), semente: int = 42) -> dict[str, list[dict]]:
    """Split determinístico por grupo (licitação). Retorna {'train','val','test'}."""
    grupos: dict[str, list[dict]] = {}
    for r in registros:
        grupos.setdefault(grupo_de(r), []).append(r)
    chaves = sorted(grupos, key=lambda g: hashlib.sha256(f"{semente}:{g}".encode()).hexdigest())
    rnd = random.Random(semente)
    rnd.shuffle(chaves)
    total = sum(len(v) for v in grupos.values())
    alvo_train, alvo_val = total * proporcoes[0], total * (proporcoes[0] + proporcoes[1])
    out = {"train": [], "val": [], "test": []}
    acumulado = 0
    for g in chaves:
        destino = "train" if acumulado < alvo_train else ("val" if acumulado < alvo_val else "test")
        out[destino].extend(grupos[g])
        acumulado += len(grupos[g])
    return out


def para_sft(r: dict) -> dict:
    return {"id": r["id"], "grupo": grupo_de(r), "prompt": montar_prompt(r["descricao"], r.get("objeto")),
            "response": montar_resposta(r["categoria"])}
