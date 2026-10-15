"""Régua por palavras para piso de borracha: o nível do sinal sobe com a combinação de termos.

Decisões de 15/10/2026 (Marcelo):
  Piso de borracha
  - só "borracha"                                                   -> fraco
  - borracha + piso                                                  -> medio
  - borracha + piso + placa + medida 1x1 m ou 50x50 cm + 15/16 mm    -> forte
  Grama sintética (avaliada antes da borracha: infill de gramado cai aqui)
  - grama sintética                                                  -> fraco
  - grama sintética + manutenção ou serviço                          -> fraco (vence rolo e aquisição)
  - grama sintética + rolo                                           -> forte
  - grama sintética + aquisição/compra                               -> forte
  - granulado + borracha + grama sintética + saco                    -> forte
  Piso modular (PP/TPE, encaixe de quadra)                           -> fora

Instalação conta como serviço (no gabarito, "instalação de grama sintética" ficou fora do escopo de produto).
v5 (soma de palavras): cada palavra soma pontos dentro da família do produto, sem depender da ordem ou da frase
(FAMILIAS no código). Piso: borracha, piso/manta/tapete/tatame, placa, medida, espessura = 1 ponto cada; 4 ou 5 = forte
(15/10), 2 a 3 = medio, 1 = fraco. Grama: grama, rolo, aquisição, society, especificação (fio em mm, fibrilado,
m²) = 2 cada; 4 = forte. Society também conta como grama na família granulado. Granulado: granulado, borracha, grama,
kg = 1 cada; 4 = forte (teste 15/10: a unidade KG entrou no lugar do saco). Serviço derruba para fraco, mas "fornecimento e instalação" não é serviço (só manutenção/reforma/recuperação).
Piso modular é fora quando o item é o piso. Família piso exige borracha no texto; EVA sem borracha sai da régua.
v4: piso, grama, granulado e borracha só contam quando são o PRODUTO (início da descrição, sem "lote 1 -" ou
"aquisição de"). Assim "fogão de piso", "halter emborrachado", "bola de borracha" e "fita para grama sintética"
não entram na régua (nivel None, o rótulo atual fica como está). Piso modular exige o termo composto.
Itens sem nenhum desses termos não são avaliados aqui (nivel None). Cada decisão devolve os sinais encontrados.

Uso:
  python3 training/regua_piso.py                     # resumo + exemplos de cada nível nos candidatos
  python3 training/regua_piso.py --exemplos 20 --csv # também grava data/regua_piso.csv para revisão
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

DADOS = Path(__file__).resolve().parent / "data"


def norm(t: str | None) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)


RE_BORRACHA = re.compile(r"\b(borracha|emborrachad[oa]s?|sbr|epdm|pneu reciclado)\b")
RE_PLACA = re.compile(r"\bplacas?\b")
# 1x1 m (1 / 1,0 / 1,00 m ou 100 cm) e 50x50 cm (50 cm ou 0,5 / 0,50 m), com ou sem unidade e espaços
_UM = r"(?:1(?:[.,]0{1,2})?\s*m?|100\s*cm|1000\s*(?:mm)?)"
_MEIO = r"(?:50\s*cm|0?[.,]50?\s*m|500\s*mm|50)"
RE_MEDIDA = re.compile(rf"\b(?:{_UM}\s*[x×]\s*{_UM}|{_MEIO}\s*[x×]\s*{_MEIO})(?:\s*(?:m|cm|mm))?\b")
# 15/16 mm, 1,5/1,6 cm ou "espessura: 15" sem unidade
RE_ESPESSURA = re.compile(r"\b(?:1[56]\s*mm|1[.,][56]\s*cm)\b|espessura( minima)?( de)?\s*:?\s*1[56]\b")
# Piso modular de quadra (plástico encaixável) é fora. Só o termo composto: "polipropileno" sozinho pegava armário e lixeira.
RE_MODULAR = re.compile(r"\b(pisos? modular(es)?|modular (de |para )?quadra|pisos? (de |em )?(encaixe|polipropileno|pp|tpe)|sistema modular)\b")
# piso modular só é fora quando o item É o piso (cabeça): "suporte com placa de encaixe" e "rodapé para pisos modulares" não
CAB_MODULAR = re.compile(r"^(\w+ ){0,2}(pisos?|quadras?|sistema modular)\b")
RE_GRAMA_PURA = re.compile(r"\b(grama|gramado|relva)s? (sintetic|artificia)")
# "society" é campo de grama sintética: conta como grama na família granulado ("granulado de borracha para campo society")
RE_SOCIETY = re.compile(r"\b(society|campo sintetico|minicampo|mini campo)\b")
RE_GRAMA = re.compile(RE_GRAMA_PURA.pattern + r"|" + RE_SOCIETY.pattern)
# especificação técnica de grama: altura do fio, mm, fibrilado/monofilamento, m², pontos por m², dtex
RE_ESPEC_GRAMA = re.compile(r"\b(\d+(?:[.,]\d+)?\s*mm|altura (do|de) fio|fibrilad[oa]s?|monofilament\w*|m2|metros? quadrados?|dtex|"
                            r"pontos por m2)\b")
RE_ROLO = re.compile(r"\brol(o|os|ao)\b")
RE_SERVICO = re.compile(r"\b(manutencao|servicos?|instalacao|instalar|reforma|recuperacao|escovacao|descompactacao|remocao|substituicao|mao de obra|execucao|esquadramento)\b")
# "fornecimento e instalação" é compra com instalação (piso monolítico, grama): não derruba para fraco.
# Só manutenção, reforma, recuperação etc. continuam sendo serviço nesse caso.
RE_FORN_INST = re.compile(r"\b(fornecimento|aquisicao|compra) e (instalacao|aplicacao|assentamento|montagem)\b|"
                          r"\b(com|incluindo|inclusive|inclusa) (a )?(instalacao|aplicacao)\b")
RE_SERVICO_PURO = re.compile(r"\b(manutencao|reforma|recuperacao|escovacao|descompactacao|remocao|substituicao|mao de obra)\b")
# EVA não é borracha (tatame de luta, tapete infantil): sem borracha de verdade, o item sai da régua
RE_EVA = re.compile(r"\be\.?v\.?a\.?\b|etil(eno)?[ -]?(vinil|acetato)|\bxpe\b|espuma")
RE_BORRACHA_REAL = re.compile(r"\b(borracha(?! (de )?e\.?v\.?a\b)|sbr|epdm|pneus?)\b")
# Tapete que não é piso: infantil, pedagógico, sensorial, amarelinha, bloco de saída, banheiro, carro
RE_TAPETE_NAO_PISO = re.compile(r"\b(infantil|pedagogic\w*|sensorial|amarelinha|alfanumeric\w*|bloco de saida|banheiro|capacho|automotiv\w*|carros?|veicul\w*)\b")
# Material escolar/artesanato: borracha de apagar, EVA em folhas
RE_ESCOLAR = re.compile(r"\b(lapis|apagar?|folhas?|glitter|artesanato)\b")
# "para manutenção de gramado" é finalidade do produto, não serviço
RE_FINALIDADE = re.compile(r"\b(para|na|de) (a )?(manutencao|reposicao|recuperacao|substituicao)\b")
RE_GRANULADO = re.compile(r"\b(granulad[oa]s?|granulos?|granulometria)\b")
RE_SACO = re.compile(r"\b(sacos?|sacarias?|big ?bags?|bags?)\b")
# Teste 15/10: na família granulado, a unidade KG substitui o saco ("25 kg", "kg", "quilos", "quilograma")
RE_KG = re.compile(r"\b(\d+(?:[.,]\d+)?\s*(kg|kgs|quilos?)|kg|kgs|quilos?|quilogramas?)\b")
RE_AQUISICAO = re.compile(r"\b(aquisicao|compra|fornecimento)\b")

# "Cabeça" = o que o item É (início da descrição, sem prefixo de lote/aquisição). Os termos de objeto (piso, grama,
# granulado, borracha como produto) só contam na cabeça: "fogão de piso", "halter emborrachado" e "fita para grama
# sintética" mencionam o termo, mas não são o produto.
RE_PREFIXO = re.compile(r"^(?:(?:lote|item|grupo|obra)\s*\d+\s*[-–:.]?\s*(?:rv\.?\s*\d+\s*-\s*)?|(?:aquisicao|fornecimento|compra)"
                        r"(?: e instalacao)? de\s+|(?:servicos? de )?(?:manutencao|instalacao|reforma|recuperacao)(?: preventiva| corretiva)?"
                        r"(?: e \w+)?(?: de| em| do| da| no| na)?\s+|servicos? de\s+|\d+\s*[-–.)]\s*)+")
RE_CORTE = re.compile(r"\s*(?::|;|\. | - |<|\(|,? especifica|,? descri)")
CAB_PISO = re.compile(r"^(pisos?|revestimento de piso)\b")
# placa, tatame, manta e tapete de borracha só viram "piso" quando a descrição diz piso; sem isso ficam como borracha (fraco)
CAB_PISO_SE_CITA = re.compile(r"^(placas?|tatames?|mantas?|tapetes?|revestimentos?)\b(?! (de )?grama)")
RE_PISO_CIT = re.compile(r"\bpisos?\b")
CAB_GRAMA = re.compile(r"^((tapete|carpete|revestimento|rolos?)( de| em)? )?(grama|gramado|relva)s? (sintetic|artificia)")
CAB_GRANULADO = re.compile(r"^(granulad[oa]s?|borracha (granulada|triturada|moida|reciclada)|composto de borracha)\b")
# borracha sozinha só conta como produto de piso (manta, lençol, rolo, granulado); borracha escolar, de raquete etc. ficam de fora
CAB_BORRACHA = re.compile(r"^(borracha|lencol de borracha|rolos? de borracha|(mantas?|tapetes?|tatames?|placas?)"
                          r" (de borracha|emborrachad\w*|sbr|epdm)|emborrachado)\b"
                          r"(?!.*\b(escolar|apagar?|lapis|raquetes?|vedacao|rodos?|portao|portas?|pes? de|elastic\w*|liga)\b)")
# "borracha" sozinha na cabeça só conta com pista de material de piso: borracha branca, plástica, nº 20 (escolar) ficam de fora
RE_BORRACHA_MATERIAL = re.compile(r"\b(lencol|mantas?|rolos?|m2|metros? quadrados?|reciclad[oa]|pneus?|sbr|epdm|pisos?|"
                                  r"espessura|granulad[oa]|placas?|tapetes?|tatames?|academia|playground)\b")


def cabeca(d: str) -> str:
    d = RE_PREFIXO.sub("", d).strip()
    return " ".join(RE_CORTE.split(d, maxsplit=1)[0].split()[:10])


# ---------------------------------------------------------------- soma de palavras
# Cada palavra vale pontos independente da ordem e de estar colada em outra ("manta de borracha 10mm para academia"
# soma manta + borracha, sem precisar da frase exata). A família é dada pelo PRODUTO na cabeça da descrição; as demais
# palavras podem aparecer em qualquer lugar do texto. Ajuste os pesos e os cortes aqui.
FAMILIAS = {
    # família: (palavras que contam e peso, corte forte, corte medio)  — abaixo do corte medio = fraco
    # 15/10: forte do piso caiu para 4 de 5 ("piso de borracha 1x1 m 15 mm" sem a palavra placa é forte)
    "piso": ({"borracha": 1, "piso": 1, "placa": 1, "medida": 1, "espessura": 1}, 4, 2),
    # 15/10: society (campo de grama sintética) e especificação técnica (fio em mm, fibrilado, m²) somam como compra
    "grama": ({"grama": 2, "rolo": 2, "aquisicao": 2, "society": 2, "especificacao": 2}, 4, None),
    "granulado": ({"granulado": 1, "borracha": 1, "grama": 1, "kg": 1}, 4, None),
}
PALAVRAS = {
    "borracha": RE_BORRACHA, "placa": RE_PLACA, "medida": RE_MEDIDA, "espessura": RE_ESPESSURA,
    "piso": re.compile(r"\b(pisos?|mantas?|tapetes?|tatames?|revestimentos?)\b"),
    "grama": RE_GRAMA, "rolo": RE_ROLO, "aquisicao": RE_AQUISICAO, "granulado": RE_GRANULADO, "saco": RE_SACO, "kg": RE_KG,
    "society": RE_SOCIETY, "especificacao": RE_ESPEC_GRAMA,
}
# Ambiente (da taxonomia de pisos v0.2 do LicitaGym): só informativo, não soma.
RE_AMBIENTE = [
    ("crossfit", re.compile(r"crossfit|cross fit|cross training|treinamento funcional|\blpo\b|levantamento (de peso )?olimpico")),
    ("academia", re.compile(r"academia|musculacao|sala de ginastica|fitness|centro de treinamento|peso livre")),
    ("playground", re.compile(r"playground|parque infantil|parquinho|recreacao|brinquedos?|escola|creche|\bcmei\b|\bemei\b|praca|condominio")),
    ("haras", re.compile(r"haras|estabulo|\bbaias?\b|cocheiras?|equin[oa]s?|cavalos?|equoterapia")),
    ("paisagismo", re.compile(r"paisagis|jardi|canteiros?|mulch|cobertura (de|do) solo")),
]


def familia(c: str) -> str | None:
    """Família pelo produto na cabeça: grama > granulado > piso (piso, placa, manta, tapete, tatame, borracha)."""
    if CAB_GRAMA.search(c):
        return "grama"
    # "borracha reciclada em manta/placa" é piso, não granulado solto
    if CAB_GRANULADO.search(c) and not (c.startswith("borracha")
                                        and re.search(r"\b(pisos?|mantas?|placas?|tapetes?|tatames?)\b", c)):
        return "granulado"
    if CAB_PISO.search(c) or CAB_PISO_SE_CITA.search(c):
        return "piso"
    if CAB_BORRACHA.search(c) and (not c.startswith("borracha") or RE_BORRACHA_MATERIAL.search(c)):
        return "piso"
    return None


def eh_servico(d: str, fam: str | None = None) -> bool:
    if fam in ("granulado", "grama") and RE_FINALIDADE.search(d) and not re.match(r"(servicos?|manutencao|reforma)\b", d):
        d = RE_FINALIDADE.sub(" ", d)
    if RE_FORN_INST.search(d):
        return bool(RE_SERVICO_PURO.search(d))
    return bool(RE_SERVICO.search(d))


def sinais(descricao: str) -> dict:
    d = norm(descricao)
    c = cabeca(d)
    fam = familia(c)
    # piso sem borracha (cerâmica, isopor, placa de sinalização, manta térmica) e EVA sem borracha de verdade saem da régua
    if fam == "piso" and (not RE_BORRACHA.search(d) or (RE_EVA.search(d) and not RE_BORRACHA_REAL.search(d))):
        fam = None
    if fam == "piso" and c.startswith("tapete") and RE_TAPETE_NAO_PISO.search(d):
        fam = None
    # granulado sem borracha (chocolate, açúcar) e borracha escolar saem da régua
    if fam == "granulado" and not RE_BORRACHA_REAL.search(d):
        fam = None
    if fam in ("piso", "granulado") and (RE_ESCOLAR.search(c) or re.search(r"\b(lapis|apagar?|glitter|artesanato)\b", d)):
        fam = None
    achadas = {k for k, rx in PALAVRAS.items() if rx.search(d)}
    pontos = 0
    if fam:
        pesos = FAMILIAS[fam][0]
        pontos = sum(pesos[k] for k in achadas if k in pesos)
    return {
        "familia": fam,
        "pontos": pontos,
        "palavras": sorted(k for k in achadas if fam and k in FAMILIAS[fam][0]),
        "servico": eh_servico(d, fam),
        "modular": bool(RE_MODULAR.search(d)) and bool(CAB_MODULAR.search(c)),
        "ambiente": next((a for a, rx in RE_AMBIENTE if rx.search(d)), None),
    }


def nivel_piso(descricao: str) -> tuple[str | None, dict]:
    """Devolve (nivel, sinais). nivel: forte | medio | fraco | fora | None (régua não se aplica).

    1. piso modular (termo composto) -> fora;
    2. sem produto da régua na cabeça -> None;
    3. serviço (manutenção, instalação, execução...) -> fraco, qualquer que seja a soma;
    4. soma >= corte forte -> forte; soma >= corte medio -> medio; senão fraco.
    """
    s = sinais(descricao)
    if s["modular"]:
        return "fora", s
    if not s["familia"]:
        return None, s
    if s["servico"]:
        return "fraco", s
    _, forte, medio = FAMILIAS[s["familia"]]
    if s["pontos"] >= forte:
        return "forte", s
    if medio is not None and s["pontos"] >= medio:
        return "medio", s
    return "fraco", s


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exemplos", type=int, default=10)
    ap.add_argument("--csv", action="store_true")
    a = ap.parse_args(argv)

    cand = [json.loads(linha) for linha in open(DADOS / "candidatos.jsonl", encoding="utf-8")]
    linhas = []
    for c in cand:
        nivel, s = nivel_piso(c.get("descricao", ""))
        if nivel:
            sin = "+".join(s["palavras"]) + ("+servico" if s["servico"] else "") + ("+modular" if s["modular"] else "")
            linhas.append({"id": c["id"], "nivel": nivel, "familia": s["familia"] or "-", "pontos": s["pontos"],
                           "sinais": sin, "ambiente": s["ambiente"] or "", "descricao": c.get("descricao", "")})
    cont = Counter(linha["nivel"] for linha in linhas)
    print(f"itens avaliados pela régua (produto piso/borracha, grama, granulado ou piso modular): {len(linhas)} de {len(cand)} candidatos")
    for k in ("forte", "medio", "fraco", "fora"):
        print(f"  {k:9s} {cont[k]:6d}")
    print("família x pontos:")
    for (fam, pts), n in sorted(Counter((linha["familia"], linha["pontos"]) for linha in linhas).items()):
        print(f"  {fam:10s} {pts} pt  {n:6d}")
    print("combinações de palavras mais comuns:")
    for comb, n in Counter(f"{linha['familia']}:{linha['sinais']}" for linha in linhas).most_common(15):
        print(f"  {n:6d}  {comb}")

    rnd = random.Random(7)
    for k in ("forte", "medio", "fraco", "fora"):
        g = [linha for linha in linhas if linha["nivel"] == k]
        print(f"\n=== {k} ({len(g)}) ===")
        for linha in rnd.sample(g, min(a.exemplos, len(g))):
            print(f"  [{linha['familia']:9s} {linha['pontos']}pt {linha['sinais']:32s}] {norm(linha['descricao'])[:95]}")

    if a.csv:
        with open(DADOS / "regua_piso.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "nivel", "familia", "pontos", "sinais", "ambiente", "descricao",
                                              "nivel_revisado", "obs"])
            w.writeheader()
            for linha in sorted(linhas, key=lambda x: ("forte", "medio", "fraco", "fora").index(x["nivel"])):
                w.writerow({**linha, "nivel_revisado": "", "obs": ""})
        print(f"\n-> {DADOS / 'regua_piso.csv'}")


if __name__ == "__main__":
    main()
