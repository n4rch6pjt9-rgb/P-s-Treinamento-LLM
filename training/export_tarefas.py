#!/usr/bin/env python3
"""Monta datasets de SFT para o Tunix a partir do que os coletores e a curadoria gravaram.

Tarefa disponível: chat_intencao — dada uma mensagem do chat da sessão (com 2 mensagens de contexto), dizer a
intenção (taxonomia da curadoria: pergunta_fornecedor, pedido_prazo, negociacao_valor, ...).

De onde vêm os rótulos:
  ouro  = training/data/curadoria/gabarito_chat.jsonl (revisão humana na aba Curadoria de Rótulos)
  prata_claude (--prata-claude) = sugestão do Claude com confiança alta (training/rotular_claude.py), sem revisão
  prata = rótulo de regra do rotular_chat.py, convertido para a intenção pela tabela MAPA_REGRA (só mensagens de
          pregoeiro/fornecedor; regra sem equivalente claro fica de fora)
Split por processo (nunca o mesmo processo em dois splits). O teste usa SÓ ouro e reúne todos os processos fora do
treino: é contra o humano que o modelo precisa provar que supera a regra. A validação (só acompanha a loss) sai de
processos do treino sem ouro e pode ter prata.

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

# Mesma taxonomia da aba de curadoria (src/api/routes/curadoria_chat.py): fonte única em config/taxonomia_chat.json
_TAX = json.loads((Path(__file__).resolve().parent / "config" / "taxonomia_chat.json").read_text(encoding="utf-8"))
VERSAO_TAXONOMIA = _TAX["versao"]
INTENCOES = {i["id"]: i["dica"] for i in _TAX["intencoes"]}


def intencao_vigente(rev: dict) -> str | None:
    """Intenção da revisão na taxonomia atual; None = categoria dividida, precisa de nova revisão humana."""
    versao, intencao = rev.get("taxonomia"), rev.get("intencao")
    if versao != VERSAO_TAXONOMIA:
        mapa = _TAX.get("migracao", {}).get(versao, {})
        if intencao in mapa:
            intencao = mapa[intencao]
    return intencao if intencao in INTENCOES else None

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


def contexto_sem_sistema(msgs: list[dict], i: int, n: int = 2, janela: int = 30) -> list[dict]:
    """As n mensagens anteriores de pessoas (pregoeiro/fornecedor), pulando avisos automáticos do sistema,
    que ocupam o contexto e escondem a pergunta a que o pregoeiro está respondendo."""
    return [x for x in msgs[max(0, i - janela): i] if x.get("autor") != "sistema"][-n:]


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


def aceites_em_lote(ouro: dict, janela_s: float = 2.0) -> set:
    """Revisões idênticas à sugestão do Claude salvas a menos de `janela_s` da revisão vizinha (Enter segurado).
    Não contam como ouro: viram prata_claude (treino/val, nunca teste)."""
    from datetime import datetime
    def ts(r):
        try:
            return datetime.fromisoformat(str(r.get("revisado_em", "")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    regs = sorted((r for r in ouro.values() if ts(r) is not None), key=ts)
    aud_arq = DADOS / "curadoria" / "lotes_auditados.json"
    auditados = json.loads(aud_arq.read_text(encoding="utf-8"))["lotes"] if aud_arq.exists() else []

    def liberado(r):  # auditoria individual ou lote aprovado por amostra (>=95%)
        if r.get("auditoria"):
            return True
        return any(r.get("processo") == a["processo"] and r.get("autor") == a["autor"]
                   and a["de"] <= str(r.get("revisado_em", ""))[:19] <= a["ate"] for a in auditados)
    lote = set()
    for i, r in enumerate(regs):
        if liberado(r) or not r.get("sugestao_intencao") or r.get("intencao") != r.get("sugestao_intencao") or r.get("obs"):
            continue
        vizinhos = [regs[j] for j in (i - 1, i + 1) if 0 <= j < len(regs)]
        if any(abs(ts(r) - ts(v)) < janela_s for v in vizinhos):
            lote.add(r["id"])
    return lote


def chat_intencao(sem_prata: bool, minimo_ouro_teste: int, piloto: bool = False, prata_claude: bool = False,
                  aceitar_lote: bool = False, sem_prata_regra: bool = False, reforco: int = 1) -> None:
    gab_arq = DADOS / "curadoria" / "gabarito_chat.jsonl"
    ouro = {}
    if gab_arq.exists():
        for r in ler_jsonl(gab_arq):
            ouro[r["id"]] = r  # última revisão vale
    lote = set() if aceitar_lote else aceites_em_lote(ouro)
    # Prata do Claude: sugestão (rotular_claude.py) com confiança alta na taxonomia atual. Só entra no treino/val.
    sugestoes = {}
    sug_arq = DADOS / "curadoria" / "sugestoes_chat.jsonl"
    if prata_claude and sug_arq.exists():
        for r in ler_jsonl(sug_arq):
            if r.get("taxonomia") == VERSAO_TAXONOMIA:
                sugestoes[r["id"]] = r  # a mais recente vale
    exemplos, origem_cont = [], Counter()
    for portal in PORTAIS:
        for arq in sorted((DADOS / portal).glob("*/chat.jsonl")) if (DADOS / portal).exists() else []:
            processo = f"{portal}:{arq.parent.name}"
            msgs = ler_jsonl(arq)
            for i, m in enumerate(msgs):
                g = ouro.get(m["id"])
                if g:
                    rotulo, fonte = intencao_vigente(g), "ouro"
                    if rotulo is None:
                        origem_cont["ouro_a_rever"] += 1  # fica fora até ser revisada na taxonomia nova
                        continue
                    m = {**m, "autor_corrigido": g.get("autor")}
                    if m["id"] in lote:
                        fonte = "prata_claude"  # aceite em lote: rótulo é do Claude, não leitura humana (fora do teste)
                elif not sem_prata and sugestoes.get(m["id"], {}).get("confianca") == "alta" \
                        and m.get("autor") in ("pregoeiro", "fornecedor"):
                    rotulo, fonte = sugestoes[m["id"]]["intencao"], "prata_claude"
                elif not sem_prata and not sem_prata_regra and m.get("autor") in ("pregoeiro", "fornecedor") \
                        and MAPA_REGRA.get(m.get("rotulo") or ""):
                    rotulo, fonte = MAPA_REGRA[m["rotulo"]], "prata"
                else:
                    continue
                if rotulo not in INTENCOES:
                    continue
                exemplos.append({"id": m["id"], "grupo": processo, "origem": fonte,
                                 "autor": m.get("autor_corrigido") or m.get("autor"),
                                 "baseline_regra": MAPA_REGRA.get(m.get("rotulo") or ""),  # o que a regra diria
                                 "prompt": prompt_de(m, contexto_sem_sistema(msgs, i)),
                                 "response": json.dumps({"categoria": rotulo}, ensure_ascii=False)})
                origem_cont[fonte] += 1
    if not exemplos:
        sys.exit("Nenhum exemplo: rode a coleta/extração e, de preferência, revise mensagens na curadoria.")

    destino = dividir_grupos([e["grupo"] for e in exemplos])
    if not piloto:
        # Ouro é escasso e fica concentrado em poucos processos: todo processo fora do treino vira TESTE (só ouro),
        # e a validação (que só acompanha a loss) sai de processos do treino SEM ouro, podendo usar prata.
        # Continua valendo: nenhum processo aparece em mais de um split.
        com_ouro = {e["grupo"] for e in exemplos if e["origem"] == "ouro"}
        for g, d in destino.items():
            if d == "val":
                destino[g] = "test"
        # Se o teste ainda tem pouco ouro, puxa processos com ouro do treino (ordem fixa por hash) até ~45% do ouro,
        # sem nunca deixar o treino com menos de 40% do ouro.
        ouro_por_grupo = Counter(e["grupo"] for e in exemplos if e["origem"] == "ouro")
        total_ouro = sum(ouro_por_grupo.values())
        alvo = min(minimo_ouro_teste, round(total_ouro * 0.45))
        no_teste = sum(n for g, n in ouro_por_grupo.items() if destino[g] == "test")
        for g in sorted((g for g in ouro_por_grupo if destino[g] == "train"),
                        key=lambda g: hashlib.sha256(f"teste:{g}".encode()).hexdigest()):
            if no_teste >= alvo:
                break
            if no_teste + ouro_por_grupo[g] <= total_ouro * 0.6:
                destino[g] = "test"
                no_teste += ouro_por_grupo[g]
        candidatos = sorted((g for g, d in destino.items() if d == "train" and g not in com_ouro),
                            key=lambda g: hashlib.sha256(f"val:{g}".encode()).hexdigest())
        n_val = max(1, round(len([d for d in destino.values() if d == "train"]) * 0.15)) if candidatos else 0
        for g in candidatos[:n_val]:
            destino[g] = "val"
    splits = {"train": [], "val": [], "test": []}
    for e in exemplos:
        d = destino[e["grupo"]]
        if d == "test" and e["origem"] != "ouro" and not piloto:
            continue  # teste só com rótulo humano (no --piloto entra prata, só para testar o encanamento)
        splits[d].append(e)
    # Reforço (oversampling) das intenções raras do fornecedor: só no TREINO; val/teste ficam intactos.
    if reforco > 1:
        lados = {i["id"]: i["lados"] for i in _TAX["intencoes"]}
        cont = Counter(json.loads(e["response"])["categoria"] for e in splits["train"])
        raras = {k for k, n in cont.items() if n < 40 and lados.get(k) == ["fornecedor"]}
        extra = [e for e in splits["train"] if json.loads(e["response"])["categoria"] in raras]
        splits["train"] += extra * (reforco - 1)
        random.Random(42).shuffle(splits["train"])
        print(f"   reforço x{reforco}: {sorted(raras)} (+{len(extra) * (reforco - 1)} exemplos no treino)")
    # Baseline justo: regra quando ela dispara; senão, a intenção mais comum daquele autor no treino
    # (sem isso o teste — só mensagens onde a regra não dispara — dá 0 para as regras e o aceite fica sem sentido).
    maioria = {}
    for autor in ("pregoeiro", "fornecedor"):
        cont = Counter(json.loads(e["response"])["categoria"] for e in splits["train"] if e.get("autor") == autor)
        if cont:
            maioria[autor] = cont.most_common(1)[0][0]
    for lst in splits.values():
        for e in lst:
            if not e["baseline_regra"]:
                e["baseline_regra"] = maioria.get(e.get("autor"), "outro")
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
    if piloto:
        print("⚠ PILOTO: val/test com rótulo de regra. Serve para ver o treino rodar; o aceite exige ouro.")
    elif len(splits["test"]) < minimo_ouro_teste:
        print(f"⚠ Teste com {len(splits['test'])} exemplos de ouro (mínimo recomendado {minimo_ouro_teste}): dá para "
              "rodar o Tunix como PILOTO (testar o encanamento), mas não para aceitar o modelo. Revise mais "
              "mensagens na Curadoria de Rótulos — fornecedores primeiro.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Datasets de SFT (Tunix) a partir da coleta e da curadoria")
    ap.add_argument("tarefa", choices=["chat_intencao"])
    ap.add_argument("--sem-prata", action="store_true", help="só exemplos revisados por humano")
    ap.add_argument("--minimo-ouro-teste", type=int, default=150)
    ap.add_argument("--reforco", type=int, default=1,
                    help="repete N vezes no treino os exemplos das intenções de fornecedor com <40 exemplos (ex.: 3)")
    ap.add_argument("--sem-prata-regra", action="store_true",
                    help="não usa a prata de regra (palavras-chave) no treino/val; só ouro e prata do Claude")
    ap.add_argument("--aceitar-lote", action="store_true",
                    help="conta como ouro também os aceites em lote da sugestão do Claude (padrão: viram prata_claude)")
    ap.add_argument("--prata-claude", action="store_true",
                    help="usa no treino/val as sugestões do Claude com confiança alta (nunca no teste)")
    ap.add_argument("--piloto", action="store_true",
                    help="preenche val/test com prata para testar o Tunix ponta a ponta (métrica NÃO vale como aceite)")
    a = ap.parse_args(argv)
    if a.tarefa == "chat_intencao":
        chat_intencao(a.sem_prata, a.minimo_ouro_teste, a.piloto, a.prata_claude, a.aceitar_lote, a.sem_prata_regra, a.reforco)


if __name__ == "__main__":
    main()
