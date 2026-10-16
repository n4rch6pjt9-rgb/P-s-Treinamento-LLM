"""Monta o dataset do classificador de escopo (SFT).

Dois passos, para que nenhum rótulo "de regra" vire gabarito sem revisão humana:

  1) coletar  -> data/candidatos.jsonl
     - itens de licitação do LicitaGym (Supabase, só service_role: rode local, nunca no Colab);
     - objetos de licitações do Sesc pela API de dados abertos (pública), para ganhar volume e variedade.
     Cada candidato leva o rótulo atual das regras (rotulo_regra), só como dica para a revisão.

  2) montar   -> data/{train,val,test}.jsonl  (formato {"id","grupo","prompt","response"})
     Junta candidatos com data/rotulos.csv (id,categoria,revisado_por) e usa SÓ linhas revisadas.
     Split 70/15/15 por licitação (itens do mesmo certame nunca vazam entre treino e teste).

Uso:
  export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
  python training/export_dataset.py coletar --sesc-ufs sp,rj,sc,go --sesc-max 400 \
      --coletor-licitagym ../LicitaGym/services/coletor-externo
  python training/rotular_gemini.py            # pré-rótulo para revisão (opcional)
  python training/export_dataset.py montar
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Garante que podemos importar módulos auxiliares na mesma pasta
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from comum import ROTULOS, dividir, normalizar, para_sft  # noqa: E402
except ImportError:
    # Fallback caso o arquivo comum.py ainda não exista ou tenha outro nome
    ROTULOS = ["forte", "fraco", "piso", "borracha", "obra_piso", "manutencao", "fora"]
    def dividir(regs, semente=42):
        import random
        random.seed(semente)
        random.shuffle(regs)
        n = len(regs)
        n_train = int(n * 0.7)
        n_val = int(n * 0.15)
        return {
            "train": regs[:n_train],
            "val": regs[n_train:n_train+n_val],
            "test": regs[n_train+n_val:]
        }
    def normalizar(texto):
        import re
        return re.sub(r'[^a-zA-Z0-9\s]', '', str(texto)).lower().strip()
    def para_sft(r):
        return {
            "id": r["id"],
            "grupo": r["grupo"],  # CORRIGIDO: era "group"
            "prompt": f"Classifique o item de licitação:\nObjeto: {r.get('objeto', '')}\nDescrição: {r['descricao']}",
            "response": r["categoria"]
        }

DADOS = Path(__file__).resolve().parent / "data"
UA = "LicitaGym-Treino/0.1 (dataset de classificacao)"  # só ASCII: a API do Sesc devolve 500 com acento no User-Agent
TERMOS_SESC = ["academia", "musculacao", "ginastica", "esteira", "equipamentos esportivos", "material esportivo",
               "piso emborrachado", "borracha", "grama sintetica", "gramado", "quadra", "tatame"]


def _get_json(url: str, headers: dict | None = None, tentativas: int = 3) -> tuple[object, dict]:
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8-sig")), dict(r.headers)
        except Exception:  # rede instável (API do Sesc derruba conexão às vezes)
            if i == tentativas - 1:
                raise
            time.sleep(4 * (i + 1))
    raise RuntimeError("inalcançável")


def coletar_supabase(url: str, chave: str) -> list[dict]:
    # O header Accept-Profile é o que diz ao Supabase para usar o schema 'public'
    h = {
        "apikey": chave, 
        "Authorization": f"Bearer {chave}",
        "Accept-Profile": "public"
    }
    
    # URL LIMPA: APENAS o nome da tabela, sem 'public.'
    lics, _ = _get_json(f"{url}/rest/v1/licitacoes_externas?select=id,objeto,fonte&limit=10000", h)
    
    objeto = {l["id"]: l for l in lics}
    out, inicio, passo = [], 0, 1000
    while True:
        # URL LIMPA aqui também: APENAS o nome da tabela
        lote, _ = _get_json(f"{url}/rest/v1/licitacao_itens?select=id,licitacao_id,descricao,categoria_escopo"
                            f"&order=id&offset={inicio}&limit={passo}", h)
        
        for it in lote:
            desc = (it.get("descricao") or "").strip()
            if len(desc) < 5:
                continue
            lic = objeto.get(it["licitacao_id"], {})
            out.append({
                "id": f"lg-{it['id']}", 
                "grupo": f"lg-{it['licitacao_id']}", 
                "origem": f"licitagym:{lic.get('fonte')}",
                "descricao": desc, 
                "objeto": lic.get("objeto"), 
                "rotulo_regra": it.get("categoria_escopo")
            })
            
        if len(lote) < passo:
            return out
        inicio += passo


def coletar_sesc(ufs: list[str], maximo_por_uf: int, pausa: float = 1.0) -> list[dict]:
    """Objetos de licitações homologadas (dataset 213). Cada licitação vira um exemplo (descricao = objeto)."""
    out, vistos = [], set()
    for uf in ufs:
        n = 0
        for termo in TERMOS_SESC + [""]:  # "" = amostra sem filtro, para ter negativos ("fora")
            if n >= maximo_por_uf:
                break
            url = (f"https://transparencia-{uf}.sesc.com.br/transparencia/dados/api/213?page=1&page_size=100"
                   f"&search={urllib.parse.quote(termo)}")
            try:
                d, _ = _get_json(url)
            except Exception as e:  # noqa: BLE001
                print(f"[sesc-{uf}] falhou '{termo}': {e}", file=sys.stderr)
                continue
            for r in (d or {}).get("registros") or []:
                chave = (uf, r.get("Ano_da_Licitacao"), r.get("Edital"))
                obj = (r.get("Descricao_do_Objeto") or "").strip()
                if n >= maximo_por_uf:
                    break
                if chave in vistos or len(obj) < 10:
                    continue
                vistos.add(chave)
                out.append({"id": f"sesc-{uf}-{chave[1]}-{chave[2]}", "grupo": f"sesc-{uf}-{chave[1]}-{chave[2]}",
                            "origem": f"sesc-{uf}", "descricao": obj, "objeto": None, "rotulo_regra": None})
                n += 1
            time.sleep(pausa)
    return out


def cmd_coletar(a) -> None:
    DADOS.mkdir(exist_ok=True)
    cand: list[dict] = []
    url, chave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if url and chave:
        cand += coletar_supabase(url.rstrip("/"), chave)
        print(f"LicitaGym: {len(cand)} itens coletados do Supabase.")
    else:
        print("AVISO: SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY ausentes: pulando itens do LicitaGym", file=sys.stderr)
        
    if a.sesc_ufs:
        s = coletar_sesc([u.strip().lower() for u in a.sesc_ufs.split(",") if u.strip()], a.sesc_max)
        print(f"Sesc: {len(s)} objetos coletados.")
        cand += s
        
    if a.coletor_licitagym:  # dica de revisão: rótulo das regras do coletor para quem ainda não tem
        try:
            sys.path.insert(0, a.coletor_licitagym)
            from coletor.escopo import classificar_texto_item  # type: ignore
            for c in cand:
                if not c.get("rotulo_regra"):
                    cat, _ = classificar_texto_item(c["descricao"])
                    c["rotulo_regra"] = "fora" if cat in (None, "catmat") else cat
        except ImportError:
            print("AVISO: Não foi possível importar o classificador do LicitaGym. Os rótulos ficarão em branco.", file=sys.stderr)

    # dedup por texto normalizado (mesmo item repetido em lotes/licitações)
    unicos, vistos = [], set()
    for c in cand:
        k = normalizar(c["descricao"]).lower()
        if k not in vistos:
            vistos.add(k)
            unicos.append(c)
            
    with open(DADOS / "candidatos.jsonl", "w", encoding="utf-8") as f:
        for c in unicos:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    print(f"✅ Sucesso! candidatos.jsonl: {len(unicos)} itens únicos (de {len(cand)} totais).")


def ler_rotulos(caminho: Path) -> dict[str, str]:
    """rotulos.csv: id,categoria,revisado_por[,obs]. Só entram linhas com revisado_por preenchido."""
    rot = {}
    if not caminho.exists():
        return rot
    with open(caminho, encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            cat = (linha.get("categoria") or "").strip()
            if (linha.get("revisado_por") or "").strip() and cat in ROTULOS:
                rot[linha["id"]] = cat
    return rot


def cmd_montar(a) -> None:
    cand = {}
    if not (DADOS / "candidatos.jsonl").exists():
        sys.exit("Erro: arquivo candidatos.jsonl não encontrado. Rode 'coletar' primeiro.")
        
    # CORRIGIDO: encoding="utf-8"
    with open(DADOS / "candidatos.jsonl", encoding="utf-8") as f:
        for linha in f:
            c = json.loads(linha)
            cand[c["id"]] = c
            
    rot = ler_rotulos(DADOS / "rotulos.csv")
    registros = [{**cand[i], "categoria": c} for i, c in rot.items() if i in cand]
    
    if not registros:
        sys.exit("Erro: nenhum rótulo revisado em data/rotulos.csv (coluna 'revisado_por' está vazia ou inexistente).")
        
    partes = dividir(registros, semente=a.semente)
    for nome, regs in partes.items():
        # CORRIGIDO: encoding="utf-8"
        with open(DADOS / f"{nome}.jsonl", "w", encoding="utf-8") as f:
            for r in regs:
                f.write(json.dumps(para_sft(r), ensure_ascii=False) + "\n")
                
    resumo = {n: dict(collections.Counter(r["categoria"] for r in regs)) | {"total": len(regs)} for n, regs in partes.items()}
    (DADOS / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    if len(registros) < 1500:
        print(f"⚠️ AVISO: {len(registros)} exemplos revisados; a meta para o SFT é 1.500–2.000.", file=sys.stderr)
    else:
        print(f"✅ Dataset montado com sucesso! Total de {len(registros)} exemplos revisados.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    
    c = sub.add_parser("coletar")
    c.add_argument("--sesc-ufs", default="", help="UFs do Sesc (ex.: sp,rj,sc,go); vazio = não coleta")
    c.add_argument("--sesc-max", type=int, default=300, help="máximo de objetos por UF")
    c.add_argument("--coletor-licitagym", metavar="DIR", help="services/coletor-externo do LicitaGym: preenche rotulo_regra")
    c.set_defaults(fn=cmd_coletar)
    
    m = sub.add_parser("montar")
    m.add_argument("--semente", type=int, default=42)
    m.set_defaults(fn=cmd_montar)
    
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()