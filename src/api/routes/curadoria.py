"""Fila de curadoria humana dos rótulos sugeridos pelo Gemini.

Lê (sem bloquear a rotulagem em andamento):
  training/data/candidatos.jsonl        -> descrições e contexto
  training/data/checkpoint_gemini.json  -> sugestões já geradas (mesmo com o script rodando)
Escreve:
  training/data/rotulos.csv             -> só linhas com revisado_por entram no treino (export_dataset.py montar)
"""
from __future__ import annotations

import csv
import json
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/curadoria", tags=["curadoria"])
pagina_router = APIRouter(tags=["curadoria"])

RAIZ = Path(__file__).resolve().parents[3]
DADOS = RAIZ / "training" / "data"
ROTULOS = ["forte", "fraco", "piso", "borracha", "obra_piso", "manutencao", "fora"]
CAMPOS = ["id", "origem", "descricao", "objeto", "rotulo_regra", "sugestao_gemini", "categoria", "revisado_por", "obs"]

_lock = threading.Lock()
_cache: dict = {}


def _candidatos() -> dict:
    p = DADOS / "candidatos.jsonl"
    if not p.exists():
        return {}
    mt = p.stat().st_mtime
    if _cache.get("cand_mt") != mt:
        cand = {}
        with open(p, encoding="utf-8") as f:
            for linha in f:
                c = json.loads(linha)
                cand[c["id"]] = c
        _cache["cand"], _cache["cand_mt"] = cand, mt
    return _cache["cand"]


def _sugestoes() -> dict:
    p = DADOS / "checkpoint_gemini.json"
    if not p.exists():
        return {}
    mt = p.stat().st_mtime
    if _cache.get("sug_mt") != mt:
        with open(p, encoding="utf-8") as f:
            _cache["sug"] = json.load(f)
        _cache["sug_mt"] = mt
    return _cache.get("sug", {})


def _revisados() -> dict:
    p = DADOS / "rotulos.csv"
    if not p.exists():
        return {}
    mt = p.stat().st_mtime
    if _cache.get("rev_mt") != mt:
        rev = {}
        with open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("revisado_por") or "").strip():
                    rev[r["id"]] = r
        _cache["rev"], _cache["rev_mt"] = rev, mt
    return _cache.get("rev", {})


def _fila(so_discordancias: bool, incluir_sem_sugestao: bool) -> list[dict]:
    cand, sug, rev = _candidatos(), _sugestoes(), _revisados()
    disc, norm = [], []
    for cid, c in cand.items():
        if cid in rev:
            continue
        s = sug.get(cid, "")
        if not s and not incluir_sem_sugestao:
            continue
        regra = c.get("rotulo_regra") or ""
        item = {"id": cid, "origem": c.get("origem") or "", "descricao": c.get("descricao") or "",
                "objeto": c.get("objeto") or "", "rotulo_regra": regra, "sugestao_gemini": s}
        (disc if (regra and s and regra != s) else norm).append(item)
    return disc if so_discordancias else disc + norm


@router.get("/stats")
def stats():
    cand, sug, rev = _candidatos(), _sugestoes(), _revisados()
    fila = _fila(False, False)
    disc = sum(1 for i in fila if i["rotulo_regra"] and i["sugestao_gemini"] and i["rotulo_regra"] != i["sugestao_gemini"])
    return {"total_candidatos": len(cand), "com_sugestao": len(sug), "revisados": len(rev),
            "pendentes_com_sugestao": len(fila), "discordancias_pendentes": disc, "rotulos": ROTULOS}


@router.get("/fila")
def fila(offset: int = 0, limite: int = 20, so_discordancias: bool = False, incluir_sem_sugestao: bool = False):
    f = _fila(so_discordancias, incluir_sem_sugestao)
    return {"total": len(f), "offset": offset, "itens": f[offset:offset + limite]}


class Decisao(BaseModel):
    id: str
    categoria: str
    obs: str = ""


class Revisao(BaseModel):
    revisado_por: str
    decisoes: list[Decisao]


@router.post("/revisar")
def revisar(r: Revisao):
    if not r.revisado_por.strip():
        raise HTTPException(status_code=422, detail="informe revisado_por")
    for d in r.decisoes:
        if d.categoria not in ROTULOS:
            raise HTTPException(status_code=422, detail=f"categoria invalida: {d.categoria}")
    cand, sug = _candidatos(), _sugestoes()
    with _lock:
        p = DADOS / "rotulos.csv"
        linhas, ordem = {}, []
        if p.exists():
            with open(p, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    if row.get("id"):
                        linhas[row["id"]] = {k: (row.get(k) or "") for k in CAMPOS}
                        ordem.append(row["id"])
        for d in r.decisoes:
            c = cand.get(d.id)
            if c is None:
                continue
            if d.id not in linhas:
                ordem.append(d.id)
            linhas[d.id] = {"id": d.id, "origem": c.get("origem") or "", "descricao": c.get("descricao") or "",
                            "objeto": c.get("objeto") or "", "rotulo_regra": c.get("rotulo_regra") or "",
                            "sugestao_gemini": sug.get(d.id, ""), "categoria": d.categoria,
                            "revisado_por": r.revisado_por.strip(), "obs": d.obs}
        tmp = p.parent / (p.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            for cid in ordem:
                w.writerow(linhas[cid])
        import os
        os.replace(tmp, p)
        _cache.pop("rev_mt", None)
        _cache.pop("rev", None)
    return {"salvas": len(r.decisoes), "stats": stats()}


HTML_PAGE = r"""
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Curadoria LicitaGym</title>
<style>
 :root{--bg:#0d1117;--card:#161b22;--bord:#30363d;--txt:#e6edf3;--mut:#8b949e;--ok:#2ea043;--warn:#d29922;--bad:#f85149}
 *{box-sizing:border-box} body{margin:0;font:14px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--txt)}
 header{display:flex;gap:10px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--bord);flex-wrap:wrap}
 .chip{background:var(--card);border:1px solid var(--bord);border-radius:999px;padding:4px 10px;color:var(--mut)}
 .chip b{color:var(--txt)}
 #barra{height:6px;background:var(--card);border:1px solid var(--bord);border-radius:3px;overflow:hidden;margin:8px 16px}
 #barra div{height:100%;background:var(--ok);width:0%}
 main{max-width:880px;margin:16px auto;padding:0 16px}
 .card{background:var(--card);border:1px solid var(--bord);border-radius:10px;padding:16px;margin-bottom:12px}
 .desc{font-size:17px;font-weight:600;margin:0 0 8px}
 .obj{color:var(--mut);margin:0 0 8px}
 .tags{display:flex;gap:8px;flex-wrap:wrap}
 .tag{border-radius:6px;padding:2px 8px;border:1px solid var(--bord);background:#0d1117}
 .tag.regra{color:var(--warn);border-color:var(--warn)}
 .tag.gemini{color:#58a6ff;border-color:#58a6ff}
 .tag.disc{color:var(--bad);border-color:var(--bad)}
 .botoes{display:flex;gap:8px;flex-wrap:wrap}
 button.cat{background:#21262d;border:1px solid var(--bord);color:var(--txt);border-radius:8px;padding:8px 12px;cursor:pointer}
 button.cat:hover{border-color:#58a6ff}
 button.cat kbd{color:var(--mut);margin-left:6px}
 button.cat.sel{border-color:var(--ok);background:#12261e}
 .acoes{display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap}
 button.pri{background:var(--ok);border:1px solid var(--ok);color:#fff;border-radius:8px;padding:8px 14px;cursor:pointer}
 input{background:#0d1117;border:1px solid var(--bord);border-radius:6px;padding:6px 8px;color:var(--txt)}
 label{color:var(--mut)}
 #toast{position:fixed;bottom:16px;right:16px;background:var(--ok);color:#fff;border-radius:8px;padding:10px 14px;display:none}
 .vazio{text-align:center;color:var(--mut);padding:40px}
</style>
</head>
<body>
<header>
  <strong>🧑‍⚖️ Curadoria de rótulos</strong>
  <span class="chip">revisados <b id="st-rev">0</b></span>
  <span class="chip">pendentes <b id="st-pend">0</b></span>
  <span class="chip">discordâncias <b id="st-disc">0</b></span>
  <label>revisor <input id="revisor" size="14"></label>
  <label><input type="checkbox" id="soDisc"> só discordâncias</label>
  <button class="pri" id="salvar">💾 Salvar lote</button>
</header>
<div id="barra"><div></div></div>
<main>
  <div class="card" id="card"></div>
  <div class="botoes" id="cats"></div>
  <div class="acoes">
    <button class="cat" id="aceitar">✅ Aceitar sugestão <kbd>Enter</kbd></button>
    <button class="cat" id="desfazer">↩️ Desfazer <kbd>Backspace</kbd></button>
    <span class="chip" id="pos"></span>
  </div>
</main>
<div id="toast"></div>
<script>
const ROTULOS = ["forte","fraco","piso","borracha","obra_piso","manutencao","fora"];
let itens=[], idx=0, lote=[], salvando=false, tt;
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const revisor = $('#revisor');
revisor.value = localStorage.getItem('curador') || '';
revisor.oninput = () => localStorage.setItem('curador', revisor.value);
function toast(m){ const t=$('#toast'); t.textContent=m; t.style.display='block'; clearTimeout(tt); tt=setTimeout(()=>t.style.display='none',2500); }

$('#cats').innerHTML = ROTULOS.map((r,i)=>`<button class="cat" data-cat="${r}">${r}<kbd>${i+1}</kbd></button>`).join('');
$('#cats').onclick = e => { const b=e.target.closest('button.cat'); if(b) decidir(b.dataset.cat); };
$('#aceitar').onclick = () => { const it=itens[idx]; if(it&&it.sugestao_gemini) decidir(it.sugestao_gemini); else toast('sem sugestão do Gemini — escolha um rótulo'); };
$('#desfazer').onclick = desfazer;
$('#salvar').onclick = async () => { await salvar(); carregaFila(); };
$('#soDisc').onchange = () => carregaFila();

async function carregaStats(){
  const s = await (await fetch('/api/curadoria/stats')).json();
  $('#st-rev').textContent=s.revisados; $('#st-pend').textContent=s.pendentes_com_sugestao; $('#st-disc').textContent=s.discordancias_pendentes;
  $('#barra').firstElementChild.style.width = (100*s.revisados/Math.max(1,s.com_sugestao)).toFixed(1)+'%';
}
async function carregaFila(){
  lote=lote; idx=0;
  const q = await (await fetch('/api/curadoria/fila?limite=20&so_discordancias='+$('#soDisc').checked)).json();
  itens=q.itens;
  if(!itens.length){ $('#card').innerHTML='<div class="vazio">🎉 Fila vazia por agora. Volte quando o Gemini avançar mais.</div>'; $('#cats').style.display='none'; }
  else { $('#cats').style.display='flex'; render(); }
  $('#pos').textContent='fila restante: '+q.total;
}
function render(){
  const it=itens[idx];
  if(!it){ carregaFila(); return; }
  const disc = it.rotulo_regra && it.sugestao_gemini && it.rotulo_regra!==it.sugestao_gemini;
  $('#card').innerHTML =
    `<p class="desc">${esc(it.descricao)}</p>
     <p class="obj">Objeto: ${esc(it.objeto||'—')}</p>
     <div class="tags">
       <span class="tag">origem: ${esc(it.origem)}</span>
       <span class="tag regra">regra: ${esc(it.rotulo_regra||'—')}</span>
       <span class="tag gemini">gemini: ${esc(it.sugestao_gemini||'—')}</span>
       ${disc?'<span class="tag disc">⚠️ discordância — revise com atenção</span>':''}
     </div>`;
  const sel=(lote.find(d=>d.id===it.id)||{}).categoria;
  document.querySelectorAll('#cats button').forEach(b=>b.classList.toggle('sel', b.dataset.cat===sel));
  $('#pos').textContent=`item ${idx+1}/${itens.length}`;
}
async function decidir(cat){
  const it=itens[idx]; if(!it) return;
  if(!revisor.value.trim()){ toast('⚠️ Informe seu nome no campo "revisor"'); revisor.focus(); return; }
  lote=lote.filter(d=>d.id!==it.id); lote.push({id:it.id, categoria:cat, obs:''});
  idx++;
  if(lote.length>=10) await salvar();
  if(idx>=itens.length){ await salvar(); carregaFila(); } else render();
}
function desfazer(){ if(idx>0){ idx--; const it=itens[idx]; lote=lote.filter(d=>d.id!==it.id); render(); } }
async function salvar(){
  if(!lote.length||salvando) return;
  salvando=true;
  const payload={revisado_por:revisor.value.trim(), decisoes:lote}; lote=[];
  try{
    const r=await fetch('/api/curadoria/revisar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!r.ok) throw new Error(await r.text());
    toast('💾 '+payload.decisoes.length+' decisões salvas');
    await carregaStats();
  }catch(e){ lote=payload.decisoes.concat(lote); toast('❌ erro ao salvar: '+e.message); }
  salvando=false;
}
document.addEventListener('keydown', e => {
  if(e.target.tagName==='INPUT') return;
  if(e.key>='1'&&e.key<='7') decidir(ROTULOS[+e.key-1]);
  else if(e.key==='Enter'){ const it=itens[idx]; if(it&&it.sugestao_gemini) decidir(it.sugestao_gemini); else toast('sem sugestão — escolha um rótulo'); }
  else if(e.key==='Backspace'){ e.preventDefault(); desfazer(); }
});
window.addEventListener('beforeunload', () => {
  if(lote.length&&revisor.value.trim())
    navigator.sendBeacon('/api/curadoria/revisar', new Blob([JSON.stringify({revisado_por:revisor.value.trim(), decisoes:lote})],{type:'application/json'}));
});
carregaStats().then(carregaFila);
</script>
</body>
</html>
"""


@pagina_router.get("/curadoria", response_class=HTMLResponse, include_in_schema=False)
def pagina():
    return HTML_PAGE
