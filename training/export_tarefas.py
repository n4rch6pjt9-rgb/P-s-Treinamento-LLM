#!/usr/bin/env python3
"""Monta datasets de SFT para o Tunix a partir do que os coletores e a curadoria gravaram.

Tarefa disponível: chat_intencao — dada uma mensagem do chat da sessão (com 2 mensagens de contexto), dizer a
intenção (taxonomia da curadoria: pergunta_fornecedor, pedido_prazo, negociacao_valor, ...).

De onde vêm os rótulos:
  ouro  = training/data/curadoria/gabarito_chat.jsonl (revisão humana na aba Curadoria de Rótulos)
  prata = rótulo de regra do rotular_chat.py, convertido para a intenção pela tabela MAPA_REGRA (só mensagens de
          pregoeiro/fornecedor; regra sem equivalente claro fica de fora)
Split por processo (nunca o mesmo processo em treino e teste). Teste e validação usam SÓ ouro: é contra o humano
que o modelo precisa provar que supera a regra. Prata só entra no treino.

Saída: training/data/tunix/chat_intencao/{train,val,test}.jsonl  ({id, grupo, origem, prompt, response})
       + rotulos.json (para o avaliar.py) + resumo.json
Uso:
    python3 training/export_tarefas.py chat_intencao
    python3 training/export_tarefas.py chat_intencao --sem-prata     # só ouro
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

DADOS = Path(__file__).resolve().parent / "data"
PORTAIS = ("sislog", "bll", "pcp")

INTENCOES = {  # mesmo vocabulário de src/api/routes/curadoria_chat.py
    "pergunta_fornecedor": "fornecedor pergunta ou pede esclarecimento",
    "pedido_prazo": "pedido de mais prazo (proposta, catálogo, documentos)",
    "desistencia_cancelamento": "cancelamento de lance ou desistência/desclassificação a pedido",
    "negociacao_valor": "negociação de valor, contraproposta, 'estamos no mínimo'",
    "envio_documentos": "aviso de envio/anexo de documentos ou proposta",
    "contestacao_concorrente": "pede verificação ou inabilitação de outra empresa",
    "argumento_recurso": "razões, contrarrazões, intenção de recurso motivada",
    "instrucao_pregoeiro": "pregoeiro orienta, convoca, cobra documento ou ajuste",
    "decisao_pregoeiro": "pregoeiro aceita, recusa, desclassifica, habilita ou declara resultado",
    "agenda_sessao": "suspensão, retomada, nova data, início de fase",
    "problema_sistema": "instabilidade, help desk, erro do portal",
    "cortesia": "saudação, agradecimento, ok",
    "outro": "nenhuma das anteriores",
}

# rótulo de regra (rotular_chat.py) -> intenção. Rótulos de mensagem automática do sistema não entram.
MAPA_REGRA = {
    "convocacao_proposta": "instrucao_pregoeiro", "convocacao_ajuste": "instrucao_pregoeiro",
    "convocacao_remanescente": "instrucao_pregoeiro", "negociacao_pedido_ajuste": "instrucao_pregoeiro",
    "negociacao_orientacao": "instrucao_pregoeiro", "orientacao_lances": "instrucao_pregoeiro",
    "alerta_inexequibilidade": "instrucao_pregoeiro", "citacao_edital": "instrucao_pregoeiro",
    "cadfor": "instrucao_pregoeiro", "diligencia_aba": "instrucao_pregoeiro", "recurso_aviso": "instrucao_pregoeiro",
    "documentos_publicados": "instrucao_pregoeiro", "em_analise": "agenda_sessao",
    "inabilitacao": "decisao_pregoeiro", "decisao_recurso": "decisao_pregoeiro",
    "desclassificacao_aviso": "decisao_pregoeiro", "resultado_analise_tecnica": "decisao_pregoeiro",
    "parecer_publicado": "decisao_pregoeiro", "parecer_item_tr": "decisao_pregoeiro",
    "declaracao_vencedor_aviso": "decisao_pregoeiro", "sem_intencao_recurso": "decisao_pregoeiro",
    "documentos_recebidos": "envio_documentos",
    "sessao_suspensa": "agenda_sessao", "sessao_retomada": "agenda_sessao", "sessao_abertura": "agenda_sessao",
    "julgamento_aviso": "agenda_sessao", "fase_lances_reestabelecida_aviso": "agenda_sessao",
    "liberado_julgamento_aviso": "agenda_sessao",
    "help_desk": "problema_sistema", "instabilidade_sistema": "problema_sistema",
    "pedido_cancelamento_lance": "desistencia_cancelamento",
    "saudacao": "cortesia",
}

INSTRUCAO = (
    "Você classifica mensagens do chat de sessões de pregão eletrônico. Leia o contexto e a MENSAGEM e responda só "
    "com JSON no formato {\"categoria\": \"<rótulo>\"}. Rótulos: "
    + "; ".join(f"{k} = {v}" for k, v in INTENCOES.items()) + "."
)


def ler_jsonl(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def corta(t: str, n: int) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def prompt_de(msg: dict, antes: list[dict]) -> str:
    linhas = [INSTRUCAO, "Contexto:"]
    for m in antes[-2:]:
        linhas.append(f"[{m.get('autor', '?')}] {corta(m.get('texto', ''), 220)}")
    if not antes:
        linhas.append("(início do chat)")
    quem = msg.get("autor_corrigido") or msg.get("autor") or "?"
    linhas.append(f"MENSAGEM [{quem}]: {corta(msg.get('texto', ''), 600)}")
    return "\n".join(linhas)


def dividir_grupos(grupos: list[str], proporcoes=(0.7, 0.15, 0.15), semente=42) -> dict[str, str]:
    chaves = sorted(set(grupos), key=lambda g: hashlib.sha256(f"{semente}:{g}".encode()).hexdigest())
    random.Random(semente).shuffle(chaves)
    n = len(chaves)
    destino = {}
    for i, g in enumerate(chaves):
        destino[g] = "train" if i < round(n * proporcoes[0]) else ("val" if i < round(n * (proporcoes[0] + proporcoes[1])) else "test")
    return destino


def chat_intencao(sem_prata: bool, minimo_ouro_teste: int) -> None:
    gab_arq = DADOS / "curadoria" / "gabarito_chat.jsonl"
    ouro = {}
    if gab_arq.exists():
        for r in ler_jsonl(gab_arq):
            ouro[r["id"]] = r  # última revisão vale
    exemplos, origem_cont = [], Counter()
    for portal in PORTAIS:
        for arq in sorted((DADOS / portal).glob("*/chat.jsonl")) if (DADOS / portal).exists() else []:
            processo = f"{portal}:{arq.parent.name}"
            msgs = ler_jsonl(arq)
            for i, m in enumerate(msgs):
                g = ouro.get(m["id"])
                if g:
                    rotulo, fonte = g["intencao"], "ouro"
                    m = {**m, "autor_corrigido": g.get("autor")}
                elif not sem_prata and m.get("autor") in ("pregoeiro", "fornecedor") and MAPA_REGRA.get(m.get("rotulo") or ""):
                    rotulo, fonte = MAPA_REGRA[m["rotulo"]], "prata"
                else:
                    continue
                if rotulo not in INTENCOES:
                    continue
                exemplos.append({"id": m["id"], "grupo": processo, "origem": fonte,
                                 "baseline_regra": MAPA_REGRA.get(m.get("rotulo") or ""),  # o que a regra diria
                                 "prompt": prompt_de(m, msgs[max(0, i - 2): i]),
                                 "response": json.dumps({"categoria": rotulo}, ensure_ascii=False)})
                origem_cont[fonte] += 1
    if not exemplos:
        sys.exit("Nenhum exemplo: rode a coleta/extração e, de preferência, revise mensagens na curadoria.")

    destino = dividir_grupos([e["grupo"] for e in exemplos])
    splits = {"train": [], "val": [], "test": []}
    for e in exemplos:
        d = destino[e["grupo"]]
        if d != "train" and e["origem"] != "ouro":
            continue  # val/test só com rótulo humano
        splits[d].append(e)
    saida = DADOS / "tunix" / "chat_intencao"
    saida.mkdir(parents=True, exist_ok=True)
    for nome, lst in splits.items():
        with open(saida / f"{nome}.jsonl", "w", encoding="utf-8") as f:
            for e in lst:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    (saida / "rotulos.json").write_text(json.dumps(list(INTENCOES), ensure_ascii=False), encoding="utf-8")
    dist = {n: dict(Counter(json.loads(e["response"])["categoria"] for e in l)) for n, l in splits.items()}
    resumo = {"tarefa": "chat_intencao", "exemplos": dict(origem_cont),
              "split": {n: len(l) for n, l in splits.items()},
              "processos": {n: len({e['grupo'] for e in l}) for n, l in splits.items()}, "distribuicao": dist}
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ chat_intencao -> {saida}")
    print(f"   origem: {dict(origem_cont)} | split: {resumo['split']} | processos: {resumo['processos']}")
    for n in ("train", "test"):
        print(f"   {n}: {dict(sorted(dist[n].items(), key=lambda x: -x[1]))}")
    if len(splits["test"]) < minimo_ouro_teste:
        print(f"⚠ Teste com {len(splits['test'])} exemplos de ouro (mínimo recomendado {minimo_ouro_teste}): dá para "
              "rodar o Tunix como PILOTO (testar o encanamento), mas não para aceitar o modelo. Revise mais "
              "mensagens na Curadoria de Rótulos — fornecedores primeiro.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Datasets de SFT (Tunix) a partir da coleta e da curadoria")
    ap.add_argument("tarefa", choices=["chat_intencao"])
    ap.add_argument("--sem-prata", action="store_true", help="só exemplos revisados por humano")
    ap.add_argument("--minimo-ouro-teste", type=int, default=150)
    a = ap.parse_args(argv)
    if a.tarefa == "chat_intencao":
        chat_intencao(a.sem_prata, a.minimo_ouro_teste)


if __name__ == "__main__":
    main()
