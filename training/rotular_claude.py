#!/usr/bin/env python3
"""Sugestões de rótulo do chat pela API do Claude (Message Batches, 50% mais barato), para a curadoria humana.

O Claude NUNCA grava no gabarito: as sugestões vão para training/data/curadoria/sugestoes_chat.jsonl e aparecem na
aba Curadoria de Rótulos como ponto de partida. Quem decide continua sendo a pessoa que revisa.

Passos:
  1) enviar   monta os pedidos e cria um lote (sem --confirmar só mostra a estimativa de custo e um exemplo)
  2) buscar   consulta o lote; quando terminar, grava as sugestões
  3) relatorio  compara sugestões com o gabarito humano (concordância por intenção)

Uso (a chave vem da variável de ambiente ANTHROPIC_API_KEY; não vai para arquivo nenhum):
    python3 training/rotular_claude.py enviar --modo calibrar              # mostra estimativa
    python3 training/rotular_claude.py enviar --modo calibrar --confirmar  # envia (mensagens já revisadas)
    python3 training/rotular_claude.py buscar --ultimo
    python3 training/rotular_claude.py relatorio
    python3 training/rotular_claude.py enviar --modo fila --confirmar      # pendentes + a revisar de novo
Modos: calibrar = só mensagens com gabarito humano válido (mede a concordância antes de gastar com o resto);
       fila = o que está na fila da curadoria (sem gabarito válido).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_tarefas import DADOS, MAPA_REGRA, PORTAIS, VERSAO_TAXONOMIA, _TAX, intencao_vigente, ler_jsonl  # noqa: E402

CURADORIA = DADOS / "curadoria"
SUGESTOES = CURADORIA / "sugestoes_chat.jsonl"
LOTES = CURADORIA / "lotes_claude"
MODELO_PADRAO = "claude-sonnet-5-5"
# US$ por milhão de tokens no Batch API (50% do preço base; tabela oficial em 2026-10). Só para a estimativa.
PRECO_LOTE = {"claude-sonnet-5-5": (1.0, 5.0), "claude-opus-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.05, 0.25)}

REGRAS_DECISAO = """Como decidir a intenção (pergunte: o que o autor quer que aconteça?):
- Classifique pelo pedido/ação, não pelo assunto. Uma pergunta que cita o TR continua sendo pergunta_esclarecimento.
- contestacao_concorrente: aponta problema na proposta, marca, preço, catálogo ou documento de OUTRA empresa
  (ex.: "a marca da empresa X já foi desclassificada antes", "valores abaixo de 50% são inexequíveis").
- contestacao_decisao: questiona uma decisão já tomada pelo pregoeiro/administração (desclassificação, reprovação de
  amostra, aceite de outro licitante). Ex.: "por que fomos desclassificados?", "solicitamos revisão da reprovação".
- reclamacao_procedimento: critica a condução do processo, não uma decisão de mérito (sem aviso prévio, horário,
  etapa pulada, falta de transparência).
- defesa_propria: justifica ou defende a própria proposta, amostra, marca ou documento ("são fotos reais do produto").
- pedido_acesso: pede para ver catálogo, proposta ou documentos de outros licitantes ou do processo.
- envio_documentos: inclui entrega (ou compromisso de entrega) de amostra física, não só de documentos.
- desistencia_cancelamento: inclui desistir de uma contestação ou recurso já iniciado ("pode seguir", "não vamos questionar").
- pergunta_esclarecimento x pedido_prazo x envio_documentos: perguntar "quando abre?" é pergunta; pedir mais tempo é
  pedido_prazo; avisar que anexou/enviou é envio_documentos.
- Se cabem duas, fique com a principal (o pedido final da mensagem). "Bom dia, segue a proposta" = envio_documentos.
- Pregoeiro — prioridade decisao_pregoeiro > instrucao_pregoeiro > resposta_esclarecimento: se a mensagem comunica um
  ato/decisão (libera, aceita, recusa, desclassifica, conclui a análise), é decisao_pregoeiro MESMO respondendo a uma
  pergunta ("Sim, vou liberar ainda hoje. Já finalizei a conferência" = decisao_pregoeiro). Se manda o fornecedor fazer
  algo, é instrucao_pregoeiro. resposta_esclarecimento só quando apenas informa/explica, sem decidir nem mandar.
- Use outro só quando nenhuma serve; diga o porquê na justificativa.
- Use as intenções do lado do autor (fornecedor ou pregoeiro). Se o autor parecer errado, classifique pelo conteúdo e
  diga isso na justificativa.
Temas (zero ou mais): o assunto concreto da mensagem. Sinais (zero ou mais): só marque quando o texto der base clara;
cita_norma exige menção explícita a edital, TR, item de edital ou lei."""


def instrucao_sistema() -> str:
    linhas = ["Você ajuda a rotular mensagens do chat de sessões de pregão eletrônico (compras públicas no Brasil) "
              "para treinar um classificador. Cada pedido traz o contexto do chat e UMA mensagem-alvo; rotule só a "
              "mensagem-alvo.", "", "Intenções (escolha exatamente uma):"]
    for i in _TAX["intencoes"]:
        linhas.append(f"- {i['id']} [{'/'.join(i['lados'])}]: {i['dica']}")
    linhas += ["", "Temas: " + "; ".join(f"{t['id']} ({t['nome']})" for t in _TAX["temas"]),
               "Sinais: " + "; ".join(f"{s['id']} ({s['nome']})" for s in _TAX["sinais"] if s["id"] != "exemplo_ouro"),
               "", REGRAS_DECISAO, "",
               "confianca: alta = um revisor experiente concordaria sem hesitar; media = há uma segunda leitura "
               "plausível; baixa = ambígua ou faltou contexto. justificativa: uma frase curta em português."]
    return "\n".join(linhas)


def esquema() -> dict:
    sinais = [s["id"] for s in _TAX["sinais"] if s["id"] != "exemplo_ouro"]  # exemplo ouro é escolha humana
    return {"type": "object", "additionalProperties": False,
            "required": ["intencao", "temas", "sinais", "confianca", "justificativa"],
            "properties": {
                "intencao": {"type": "string", "enum": [i["id"] for i in _TAX["intencoes"]]},
                "temas": {"type": "array", "items": {"type": "string", "enum": [t["id"] for t in _TAX["temas"]]}},
                "sinais": {"type": "array", "items": {"type": "string", "enum": sinais}},
                "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                "justificativa": {"type": "string"}}}


def _linha(m: dict) -> str:
    quem = m.get("autor") or "?"
    emp = f" ({m['empresa']})" if m.get("empresa") else ""
    return f"[{(m.get('data_hora_brasilia') or '')[:16]}] {quem}{emp}: {' '.join((m.get('texto') or '').split())[:700]}"


def conteudo(msgs: list[dict], i: int, processo: str, autor_gab: str | None) -> str:
    m = msgs[i]
    antes = [_linha(x) for x in msgs[max(0, i - 4): i]] or ["(início do chat)"]
    depois = [_linha(x) for x in msgs[i + 1: i + 3]]
    autor = autor_gab or m.get("autor") or "?"
    lotes = f" · lote(s) {', '.join(map(str, m['lotes']))}" if m.get("lotes") else ""
    return "\n".join([f"Processo {processo}{lotes}", "Contexto anterior:", *antes,
                      "", f"MENSAGEM-ALVO (autor: {autor}):", _linha({**m, "autor": autor}),
                      "", "Mensagens seguintes (só contexto):", *(depois or ["(fim do chat)"])])


def _entra_na_fila(m: dict) -> bool:  # mesmo critério da API de curadoria
    if m.get("autor") == "sistema":
        return False
    if "status" in m:
        return m["status"] == "pendente_llm"
    return m.get("autor") in ("fornecedor", "pregoeiro", "indeterminado")


def selecionar(modo: str, limite: int | None, portal: str | None) -> list[tuple[str, str]]:
    """[(id, texto do pedido)] conforme o modo."""
    gab = {}
    arq = CURADORIA / "gabarito_chat.jsonl"
    if arq.exists():
        for r in ler_jsonl(arq):
            gab[r["id"]] = r
    ja_sugerido = set()
    sug_atual = {}
    if modo == "resposta":  # reavalia tudo que hoje está como resposta_esclarecimento (ouro ou sugestão)
        sug = CURADORIA / "sugestoes_chat.jsonl"
        if sug.exists():
            for r in ler_jsonl(sug):
                if r.get("taxonomia") == VERSAO_TAXONOMIA:
                    sug_atual[r["id"]] = r["intencao"]
    if modo == "prata":  # não repete mensagens que já têm sugestão na taxonomia atual
        sug = CURADORIA / "sugestoes_chat.jsonl"
        if sug.exists():
            ja_sugerido = {r["id"] for r in ler_jsonl(sug) if r.get("taxonomia") == VERSAO_TAXONOMIA}
    saida = []
    for p in PORTAIS:
        if portal and p != portal:
            continue
        for a in sorted((DADOS / p).glob("*/chat.jsonl")) if (DADOS / p).exists() else []:
            msgs = ler_jsonl(a)
            for i, m in enumerate(msgs):
                g = gab.get(m["id"])
                valido = g is not None and intencao_vigente(g) is not None
                if modo == "calibrar" and not valido:
                    continue
                if modo == "fila" and (valido or not (_entra_na_fila(m) or g is not None)):
                    continue
                if modo == "prata" and (valido or m["id"] in ja_sugerido or m.get("autor") not in ("pregoeiro", "fornecedor")
                                        or not MAPA_REGRA.get(m.get("rotulo") or "")):
                    continue  # só as que hoje entram no treino como prata de regra
                if modo == "resposta":
                    atual = intencao_vigente(g) if valido else sug_atual.get(m["id"])
                    if atual != "resposta_esclarecimento":
                        continue
                saida.append((m["id"], conteudo(msgs, i, f"{p}:{a.parent.name}", (g or {}).get("autor"))))
    return saida[:limite] if limite else saida


def pedido(custom_id: str, texto: str, modelo: str, sistema: str) -> dict:
    return {"custom_id": custom_id, "params": {
        "model": modelo, "max_tokens": 600,
        "thinking": {"type": "between_tools"},  # sem raciocínio prévio: classificação curta e barata
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": esquema()}},
        "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": texto}]}}


def cliente():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Defina ANTHROPIC_API_KEY no terminal (ex.: no ~/.bashrc). A chave não deve ir para arquivo do repo.")
    try:
        import anthropic
    except ImportError:
        sys.exit("Instale o SDK: pip install anthropic")
    return anthropic.Anthropic()


def cmd_enviar(a) -> None:
    sistema = instrucao_sistema()
    itens = selecionar(a.modo, a.limite, a.portal)
    if not itens:
        sys.exit("Nada para enviar nesse modo.")
    tok_sis, tok_msg = len(sistema) / 3.2, sum(len(t) for _, t in itens) / 3.2  # estimativa grosseira (pt-BR)
    pin, pout = PRECO_LOTE.get(a.modelo, (1.0, 5.0))
    custo = (len(itens) * tok_sis * 0.1 + tok_sis + tok_msg) / 1e6 * pin + len(itens) * 120 / 1e6 * pout
    custo_sem_cache = (len(itens) * tok_sis + tok_msg) / 1e6 * pin + len(itens) * 120 / 1e6 * pout
    print(f"{len(itens)} mensagens · modelo {a.modelo} · modo {a.modo}")
    print(f"estimativa: ~US$ {custo:.2f} com cache das instruções (até ~US$ {custo_sem_cache:.2f} sem cache)")
    if not a.confirmar:
        print("\n--- exemplo de pedido ---\n" + itens[0][1] + "\n---\nNada foi enviado. Rode de novo com --confirmar.")
        return
    c = cliente()
    lote = c.messages.batches.create(requests=[pedido(i, t, a.modelo, sistema) for i, t in itens])
    LOTES.mkdir(parents=True, exist_ok=True)
    (LOTES / f"{lote.id}.json").write_text(json.dumps({
        "lote": lote.id, "modelo": a.modelo, "modo": a.modo, "taxonomia": VERSAO_TAXONOMIA, "n": len(itens),
        "criado_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}, ensure_ascii=False, indent=1))
    print(f"✅ lote {lote.id} criado ({lote.processing_status}). Depois: python3 training/rotular_claude.py buscar --ultimo")


def _ultimo_lote() -> str:
    arqs = sorted(LOTES.glob("*.json"), key=lambda p: p.stat().st_mtime) if LOTES.exists() else []
    if not arqs:
        sys.exit("Nenhum lote registrado em training/data/curadoria/lotes_claude/.")
    return arqs[-1].stem


def cmd_buscar(a) -> None:
    lote_id = a.lote or _ultimo_lote()
    meta = json.loads((LOTES / f"{lote_id}.json").read_text(encoding="utf-8"))
    c = cliente()
    lote = c.messages.batches.retrieve(lote_id)
    rc = lote.request_counts
    print(f"lote {lote_id}: {lote.processing_status} · ok {rc.succeeded} · erro {rc.errored} · "
          f"processando {rc.processing} · expirado {rc.expired}")
    if lote.processing_status != "ended":
        print("Ainda processando (costuma levar minutos; no máximo 24 h). Rode de novo mais tarde.")
        return
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    linhas, falhas, uso = [], Counter(), Counter()
    for r in c.messages.batches.results(lote_id):
        if r.result.type != "succeeded":
            falhas[r.result.type] += 1
            continue
        msg = r.result.message
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            uso[k] += getattr(msg.usage, k, 0) or 0
        texto = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            s = json.loads(texto)
        except json.JSONDecodeError:
            falhas["json_invalido"] += 1
            continue
        linhas.append({"id": r.custom_id, **s, "intencao": s["intencao"].lower(), "modelo": meta["modelo"],
                       "taxonomia": meta["taxonomia"], "lote": lote_id, "gerado_em": agora})
    CURADORIA.mkdir(parents=True, exist_ok=True)
    with open(SUGESTOES, "a", encoding="utf-8") as f:
        for l in linhas:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    pin, pout = PRECO_LOTE.get(meta["modelo"], (1.0, 5.0))
    custo = ((uso["input_tokens"] + uso["cache_creation_input_tokens"] * 1.25 + uso["cache_read_input_tokens"] * 0.1)
             * pin + uso["output_tokens"] * pout) / 1e6
    print(f"✅ {len(linhas)} sugestões gravadas em {SUGESTOES.relative_to(DADOS.parent.parent)}"
          f"{' · falhas: ' + str(dict(falhas)) if falhas else ''}")
    print(f"   tokens: {dict(uso)} · custo aproximado US$ {custo:.2f}")
    if meta["modo"] == "calibrar":
        print("   Agora: python3 training/rotular_claude.py relatorio")


def carregar_sugestoes() -> dict:
    sug = {}
    if SUGESTOES.exists():
        for s in ler_jsonl(SUGESTOES):
            if s.get("taxonomia") == VERSAO_TAXONOMIA:
                sug[s["id"]] = s  # a mais recente vale
    return sug


def cmd_relatorio(a) -> None:
    sug = carregar_sugestoes()
    gab = {r["id"]: r for r in ler_jsonl(CURADORIA / "gabarito_chat.jsonl")} if (CURADORIA / "gabarito_chat.jsonl").exists() else {}
    pares = [(intencao_vigente(g), sug[i]) for i, g in gab.items() if i in sug and intencao_vigente(g)]
    if not pares:
        sys.exit("Sem pares sugestão × gabarito na taxonomia atual. Rode enviar --modo calibrar e buscar.")
    acertos = sum(h == s["intencao"] for h, s in pares)
    print(f"Concordância Claude × humano (intenção): {acertos}/{len(pares)} = {acertos / len(pares):.0%}\n")
    por = defaultdict(lambda: [0, 0])
    for h, s in pares:
        por[h][1] += 1
        por[h][0] += h == s["intencao"]
    print(f"{'intenção (humano)':28} {'acerto':>8}  n")
    for k, (ok, n) in sorted(por.items(), key=lambda x: -x[1][1]):
        print(f"{k:28} {ok / n:>8.0%}  {n}")
    conf = defaultdict(lambda: [0, 0])
    for h, s in pares:
        conf[s["confianca"]][1] += 1
        conf[s["confianca"]][0] += h == s["intencao"]
    print("\nPor confiança declarada: " + " · ".join(f"{k} {ok / n:.0%} (n={n})" for k, (ok, n) in conf.items()))
    trocas = Counter(f"{h} -> {s['intencao']}" for h, s in pares if h != s["intencao"])
    if trocas:
        print("\nPrincipais divergências (humano -> Claude):")
        for k, v in trocas.most_common(10):
            print(f"  {v:3}  {k}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Sugestões de rótulo do chat pela API do Claude (Batch)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enviar")
    e.add_argument("--modo", choices=["calibrar", "fila", "prata", "resposta"], required=True)
    e.add_argument("--modelo", default=MODELO_PADRAO)
    e.add_argument("--limite", type=int)
    e.add_argument("--portal", choices=PORTAIS)
    e.add_argument("--confirmar", action="store_true", help="sem isso, só mostra estimativa e exemplo")
    b = sub.add_parser("buscar")
    b.add_argument("--lote")
    b.add_argument("--ultimo", action="store_true")
    sub.add_parser("relatorio")
    a = ap.parse_args(argv)
    {"enviar": cmd_enviar, "buscar": cmd_buscar, "relatorio": cmd_relatorio}[a.cmd](a)


if __name__ == "__main__":
    main()
