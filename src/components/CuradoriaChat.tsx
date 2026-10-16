/**
 * Curadoria humana do chat e das decisões coletadas nos portais (SISLOG, BLL, Portal de Compras Públicas).
 * Fala com a API local (src/api, FastAPI): uvicorn main:app --port 8000, rodando dentro de src/api.
 * Nada de chave no navegador: só lê a fila e grava a revisão em training/data/curadoria/*.jsonl via API.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ChevronRight, Gavel, MessagesSquare, RefreshCw, Server, Star, AlertTriangle } from 'lucide-react';

type Opcao = { id: string; nome: string; dica?: string };
type Taxonomia = { versao: string; intencoes: Opcao[]; marcas: Opcao[]; decisoes: string[]; motivos: string[] };
type Msg = { id: string; data_hora?: string; autor?: string; empresa?: string; rotulo_regra?: string; texto: string };
type ItemChat = Msg & { portal: string; processo: string; lotes: number[]; antes: Msg[]; depois: Msg[] };
type ItemDecisao = {
  id: string; portal: string; processo: string; tipo?: string; subtipo?: string; documento?: string;
  empresa?: string; recorrente?: string; decisao_regra?: string; categorias_regra: string[]; ementa?: string;
  alertas: string[]; texto: string; lotes?: number[]; lote?: number;
};
type Stats = {
  por_portal: Record<string, { processos: number; mensagens: number; na_fila: number; revisadas: number }>;
  decisoes: number; decisoes_revisadas: number;
};

const API_PADRAO = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
const TECLAS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'q', 'w', 'e', 'r'];
const ler = (k: string, padrao: string) => { try { return localStorage.getItem(k) || padrao; } catch { return padrao; } };
const gravar = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* sem storage: segue */ } };

const corAutor = (a?: string) =>
  a === 'fornecedor' ? 'bg-amber-50 text-amber-800 border-amber-200'
    : a === 'pregoeiro' ? 'bg-blue-50 text-blue-800 border-blue-200'
      : a === 'sistema' ? 'bg-slate-100 text-slate-600 border-slate-200'
        : 'bg-rose-50 text-rose-700 border-rose-200';

const Linha: React.FC<{ m: Msg; destaque?: boolean }> = ({ m, destaque }) => (
  <div className={`flex gap-3 px-3 py-2 rounded-lg ${destaque ? 'bg-white border-2 border-indigo-300 shadow-sm' : 'opacity-70'}`}>
    <div className="w-36 shrink-0 text-[11px] font-mono text-slate-400 pt-0.5">{(m.data_hora || '').replace('T', ' ').slice(0, 19)}</div>
    <div className="flex-1 min-w-0">
      <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
        <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${corAutor(m.autor)}`}>{m.autor || '?'}</span>
        {m.empresa && <span className="text-[11px] text-slate-500 truncate">{m.empresa}</span>}
        {m.rotulo_regra && <span className="text-[10px] font-mono text-slate-400">regra: {m.rotulo_regra}</span>}
      </div>
      <p className={`whitespace-pre-wrap break-words ${destaque ? 'text-[15px] text-slate-900' : 'text-sm text-slate-600'}`}>{m.texto}</p>
    </div>
  </div>
);

export const CuradoriaChat: React.FC = () => {
  const [api, setApi] = useState(() => ler('curadoria.api', API_PADRAO));
  const [revisor, setRevisor] = useState(() => ler('curadoria.revisor', ''));
  const [aba, setAba] = useState<'chat' | 'decisoes'>('chat');
  const [tax, setTax] = useState<Taxonomia | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [portal, setPortal] = useState('');
  const [autor, setAutor] = useState('');
  const [fila, setFila] = useState<ItemChat[]>([]);
  const [total, setTotal] = useState(0);
  const [pulados, setPulados] = useState(0);
  const [marcas, setMarcas] = useState<string[]>([]);
  const [obs, setObs] = useState('');
  const [autorCorrigido, setAutorCorrigido] = useState('');
  const [decs, setDecs] = useState<ItemDecisao[]>([]);
  const [totalDec, setTotalDec] = useState(0);
  const [decisao, setDecisao] = useState('');
  const [motivos, setMotivos] = useState<string[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const req = useCallback(async (caminho: string, corpo?: unknown) => {
    const r = await fetch(`${api.replace(/\/$/, '')}/api/curadoria-chat${caminho}`, corpo === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
    });
    if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`);
    return r.json();
  }, [api]);

  const limpar = () => { setMarcas([]); setObs(''); setAutorCorrigido(''); setDecisao(''); setMotivos([]); };

  const carregar = useCallback(async () => {
    try {
      setErro(null);
      const [t, s] = await Promise.all([req('/taxonomia'), req('/stats')]);
      setTax(t); setStats(s);
      if (aba === 'chat') {
        const q = new URLSearchParams({ offset: String(pulados), limite: '15', portal, autor });
        const f = await req(`/fila?${q}`);
        setFila(f.itens); setTotal(f.total);
      } else {
        const f = await req(`/decisoes?offset=${pulados}&limite=5`);
        setDecs(f.itens); setTotalDec(f.total);
      }
      limpar();
    } catch (e: any) {
      setErro(String(e?.message || e));
    }
  }, [req, aba, portal, autor, pulados]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { gravar('curadoria.api', api); }, [api]);
  useEffect(() => { gravar('curadoria.revisor', revisor); }, [revisor]);

  const atual = fila[0];
  const decAtual = decs[0];

  const salvarChat = useCallback(async (intencao: string) => {
    if (!atual || salvando) return;
    if (!revisor.trim()) { setAviso('Informe seu nome em "Revisor" antes de salvar.'); return; }
    setSalvando(true);
    try {
      await req('/revisar', { revisado_por: revisor, revisoes: [{ id: atual.id, intencao, marcas, obs, autor_corrigido: autorCorrigido || null }] });
      setFila(f => f.slice(1)); setTotal(t => t - 1); limpar(); setAviso(null);
      if (fila.length <= 2) carregar();
    } catch (e: any) { setAviso(`Não salvou: ${e?.message || e}`); } finally { setSalvando(false); }
  }, [atual, salvando, revisor, req, marcas, obs, autorCorrigido, fila.length, carregar]);

  const salvarDecisao = useCallback(async () => {
    if (!decAtual || !decisao || salvando) return;
    if (!revisor.trim()) { setAviso('Informe seu nome em "Revisor" antes de salvar.'); return; }
    setSalvando(true);
    try {
      await req('/revisar-decisao', { revisado_por: revisor, revisoes: [{ id: decAtual.id, decisao, motivos, marcas, obs }] });
      setDecs(d => d.slice(1)); setTotalDec(t => t - 1); limpar(); setAviso(null);
      if (decs.length <= 2) carregar();
    } catch (e: any) { setAviso(`Não salvou: ${e?.message || e}`); } finally { setSalvando(false); }
  }, [decAtual, decisao, salvando, revisor, req, motivos, marcas, obs, decs.length, carregar]);

  const pular = () => {
    if (aba === 'chat') { setFila(f => f.slice(1)); if (fila.length <= 2) setPulados(p => p + 15); }
    else { setDecs(d => d.slice(1)); if (decs.length <= 2) setPulados(p => p + 5); }
    limpar();
  };

  // atalhos: 1-9, q w e r = intenção (salva); → pula
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      if (alvo && ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo.tagName)) return;
      if (aba !== 'chat' || !tax) return;
      const i = TECLAS.indexOf(e.key.toLowerCase());
      if (i >= 0 && tax.intencoes[i]) { e.preventDefault(); salvarChat(tax.intencoes[i].id); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); pular(); }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  });

  const alternar = (lista: string[], set: (v: string[]) => void, v: string) =>
    set(lista.includes(v) ? lista.filter(x => x !== v) : [...lista, v]);

  const portais = useMemo(() => Object.keys(stats?.por_portal || {}), [stats]);

  return (
    <div className="space-y-6">
      {/* Cabeçalho */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Curadoria de Rótulos</h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Revise o que a regra não resolveu no chat das sessões e as decisões (recursos, pareceres, ratificações).
            Cada revisão vira gabarito em <code className="text-xs bg-slate-100 px-1 rounded">training/data/curadoria/</code>.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <label className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2 py-1.5">
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <input value={api} onChange={e => setApi(e.target.value)} className="w-44 outline-none font-mono" aria-label="Endereço da API" />
          </label>
          <input value={revisor} onChange={e => setRevisor(e.target.value)} placeholder="Revisor (seu nome)"
            className="bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 w-40 outline-none focus:border-indigo-400" />
          <button onClick={carregar} className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-900 text-white font-semibold">
            <RefreshCw className="w-3.5 h-3.5" /> Atualizar
          </button>
        </div>
      </div>

      {erro && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <div className="font-bold flex items-center gap-1.5 mb-1"><AlertTriangle className="w-4 h-4" /> API de curadoria fora do ar</div>
          <p className="mb-2">Não consegui falar com <code>{api}</code> ({erro}). No terminal, na pasta do repositório:</p>
          <pre className="bg-white/70 rounded-lg p-2 text-xs overflow-x-auto">cd src/api && pip install -r requirements.txt && uvicorn main:app --port 8000</pre>
        </div>
      )}

      {/* Placar */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {portais.map(p => {
            const s = stats.por_portal[p];
            const pct = s.na_fila ? Math.round((100 * s.revisadas) / s.na_fila) : 0;
            return (
              <button key={p} onClick={() => { setPortal(portal === p ? '' : p); setPulados(0); }}
                className={`text-left rounded-xl border p-3 bg-white transition ${portal === p ? 'border-indigo-400 ring-2 ring-indigo-100' : 'border-slate-200 hover:border-slate-300'}`}>
                <div className="text-[11px] uppercase font-bold text-slate-400 tracking-wide">{p}</div>
                <div className="text-lg font-extrabold text-slate-900">{s.revisadas}<span className="text-slate-400 font-semibold text-sm"> / {s.na_fila}</span></div>
                <div className="text-[11px] text-slate-500">{s.processos} processos · {s.mensagens} mensagens</div>
                <div className="h-1 bg-slate-100 rounded mt-2"><div className="h-1 bg-emerald-500 rounded" style={{ width: `${pct}%` }} /></div>
              </button>
            );
          })}
          <div className="rounded-xl border border-slate-200 p-3 bg-white">
            <div className="text-[11px] uppercase font-bold text-slate-400 tracking-wide">decisões</div>
            <div className="text-lg font-extrabold text-slate-900">{stats.decisoes_revisadas}<span className="text-slate-400 font-semibold text-sm"> / {stats.decisoes}</span></div>
            <div className="text-[11px] text-slate-500">recursos, pareceres, ratificações</div>
          </div>
        </div>
      )}

      {/* Abas */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex p-1 bg-slate-100 rounded-xl text-xs font-semibold">
          {(['chat', 'decisoes'] as const).map(a => (
            <button key={a} onClick={() => { setAba(a); setPulados(0); }}
              className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 ${aba === a ? 'bg-white shadow-2xs text-slate-900' : 'text-slate-600'}`}>
              {a === 'chat' ? <MessagesSquare className="w-3.5 h-3.5" /> : <Gavel className="w-3.5 h-3.5" />}
              {a === 'chat' ? `Chat (${total})` : `Decisões (${aba === 'decisoes' ? totalDec : stats ? stats.decisoes - stats.decisoes_revisadas : 0})`}
            </button>
          ))}
        </div>
        {aba === 'chat' && (
          <select value={autor} onChange={e => { setAutor(e.target.value); setPulados(0); }}
            className="text-xs bg-white border border-slate-200 rounded-lg px-2 py-1.5">
            <option value="">todos os autores</option>
            <option value="fornecedor">fornecedor</option>
            <option value="pregoeiro">pregoeiro</option>
            <option value="indeterminado">indeterminado</option>
          </select>
        )}
        {aviso && <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1">{aviso}</span>}
      </div>

      {/* CHAT */}
      {aba === 'chat' && tax && (atual ? (
        <div className="grid lg:grid-cols-[1fr_320px] gap-5">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-3 space-y-1.5">
            <div className="flex items-center gap-2 px-2 pb-2 text-xs text-slate-500">
              <span className="font-bold uppercase">{atual.portal}</span><ChevronRight className="w-3 h-3" />
              <span className="font-mono">{atual.processo}</span>
              {atual.lotes?.length > 0 && <span>· lote(s) {atual.lotes.join(', ')}</span>}
            </div>
            {atual.antes.map(m => <Linha key={m.id} m={m} />)}
            <Linha m={atual} destaque />
            {atual.depois.map(m => <Linha key={m.id} m={m} />)}
          </div>

          <div className="space-y-4">
            <div>
              <div className="text-[11px] font-bold uppercase text-slate-400 mb-1.5">Intenção (tecla salva)</div>
              <div className="grid gap-1.5">
                {tax.intencoes.map((o, i) => (
                  <button key={o.id} onClick={() => salvarChat(o.id)} disabled={salvando} title={o.dica}
                    className="flex items-center gap-2 text-left text-sm px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 hover:border-indigo-400 hover:bg-indigo-50 disabled:opacity-50">
                    <kbd className="text-[10px] font-mono w-5 text-center rounded bg-slate-100 border border-slate-200">{TECLAS[i]}</kbd>
                    <span className="flex-1">{o.nome}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase text-slate-400 mb-1.5">Marcas (antes de salvar)</div>
              <div className="flex flex-wrap gap-1.5">
                {tax.marcas.map(m => (
                  <button key={m.id} onClick={() => alternar(marcas, setMarcas, m.id)}
                    className={`text-xs px-2 py-1 rounded-full border ${marcas.includes(m.id) ? 'bg-amber-100 border-amber-300 text-amber-900' : 'bg-white border-slate-200 text-slate-600'}`}>
                    {m.id === 'exemplo_ouro' && <Star className="inline w-3 h-3 mr-0.5 -mt-0.5" />}{m.nome}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select value={autorCorrigido} onChange={e => setAutorCorrigido(e.target.value)}
                className="text-xs bg-white border border-slate-200 rounded-lg px-2 py-1.5">
                <option value="">autor: {atual.autor}</option>
                <option value="fornecedor">corrigir: fornecedor</option>
                <option value="pregoeiro">corrigir: pregoeiro</option>
                <option value="sistema">corrigir: sistema</option>
              </select>
              <button onClick={pular} className="text-xs px-2 py-1.5 rounded-lg border border-slate-200 bg-white">Pular (→)</button>
            </div>
            <textarea value={obs} onChange={e => setObs(e.target.value)} rows={2} placeholder="Observação (opcional)"
              className="w-full text-sm bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-indigo-400" />
          </div>
        </div>
      ) : !erro && <Vazio texto="Nada pendente no chat com esse filtro." />)}

      {/* DECISÕES */}
      {aba === 'decisoes' && tax && (decAtual ? (
        <div className="grid lg:grid-cols-[1fr_320px] gap-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-bold uppercase">{decAtual.portal}</span><ChevronRight className="w-3 h-3" />
              <span className="font-mono">{decAtual.processo}</span>
              <span className="px-1.5 py-0.5 rounded bg-slate-100 font-mono">{decAtual.subtipo || decAtual.tipo}</span>
              {decAtual.decisao_regra && <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 font-semibold">regra: {decAtual.decisao_regra}</span>}
            </div>
            <div className="text-sm font-semibold text-slate-800 break-words">{decAtual.documento}</div>
            {(decAtual.empresa || decAtual.recorrente) && (
              <div className="text-xs text-slate-600">
                {decAtual.recorrente && <>Recorrente: <b>{decAtual.recorrente}</b> · </>}
                {decAtual.empresa && <>Empresa: <b>{decAtual.empresa}</b></>}
              </div>
            )}
            {decAtual.alertas.map(a => (
              <div key={a} className="text-xs rounded-lg bg-amber-50 border border-amber-200 text-amber-900 px-2 py-1.5 flex gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{a}
              </div>
            ))}
            {decAtual.ementa && <p className="text-xs bg-slate-50 rounded-lg p-2 text-slate-700"><b>Ementa:</b> {decAtual.ementa}</p>}
            <div className="max-h-[420px] overflow-y-auto text-sm text-slate-700 whitespace-pre-wrap border-t border-slate-100 pt-3">{decAtual.texto}</div>
          </div>
          <div className="space-y-4">
            <div>
              <div className="text-[11px] font-bold uppercase text-slate-400 mb-1.5">Decisão</div>
              <div className="flex flex-wrap gap-1.5">
                {tax.decisoes.map(d => (
                  <button key={d} onClick={() => setDecisao(d)}
                    className={`text-xs px-2 py-1 rounded-lg border ${decisao === d ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-slate-200 text-slate-700'}`}>{d}</button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase text-slate-400 mb-1.5">Motivos</div>
              <div className="flex flex-wrap gap-1.5">
                {tax.motivos.map(m => (
                  <button key={m} onClick={() => alternar(motivos, setMotivos, m)}
                    className={`text-xs px-2 py-1 rounded-full border ${motivos.includes(m) ? 'bg-amber-100 border-amber-300 text-amber-900' : decAtual.categorias_regra.includes(m) ? 'bg-white border-indigo-300 text-indigo-700' : 'bg-white border-slate-200 text-slate-600'}`}>{m}</button>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {tax.marcas.map(m => (
                <button key={m.id} onClick={() => alternar(marcas, setMarcas, m.id)}
                  className={`text-xs px-2 py-1 rounded-full border ${marcas.includes(m.id) ? 'bg-amber-100 border-amber-300 text-amber-900' : 'bg-white border-slate-200 text-slate-600'}`}>{m.nome}</button>
              ))}
            </div>
            <textarea value={obs} onChange={e => setObs(e.target.value)} rows={3} placeholder="Observação (ex.: item, cláusula do TR)"
              className="w-full text-sm bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-indigo-400" />
            <div className="grid grid-cols-2 gap-2">
              <button onClick={pular} className="text-xs px-2 py-2 rounded-lg border border-slate-200 bg-white">Pular</button>
              <button onClick={salvarDecisao} disabled={!decisao || salvando}
                className="text-xs px-2 py-2 rounded-lg bg-emerald-600 text-white font-semibold disabled:opacity-40 inline-flex items-center justify-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Salvar
              </button>
            </div>
          </div>
        </div>
      ) : !erro && <Vazio texto="Nenhuma decisão pendente." />)}
    </div>
  );
};

const Vazio: React.FC<{ texto: string }> = ({ texto }) => (
  <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">{texto}</div>
);
