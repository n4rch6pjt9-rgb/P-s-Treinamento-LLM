/**
 * Curadoria humana do chat e das decisões coletadas nos portais (SISLOG, BLL, Portal de Compras Públicas).
 * Fala com a API local (src/api, FastAPI): uvicorn main:app --port 8000, rodando dentro de src/api.
 * Nada de chave no navegador: só lê a fila e grava a revisão em training/data/curadoria/*.jsonl via API.
 *
 * Layout pensado para revisar em sequência pelo teclado: modo foco em tela cheia, conversa à esquerda,
 * painel de decisão fixo à direita, voltar (←) para corrigir a anterior e ajuda de atalhos (?).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, ChevronRight, Keyboard, Maximize2, Minimize2,
  RefreshCw, Search, Settings, Sparkles, Star,
} from 'lucide-react';

type Opcao = { id: string; nome: string; dica?: string; lados?: string[] };
type Taxonomia = {
  versao: string; intencoes: Opcao[]; temas: Opcao[]; sinais: Opcao[]; marcas: Opcao[]; decisoes: string[]; motivos: string[];
};
type Revisao = { intencao: string; taxonomia?: string; marcas?: string[]; sinais?: string[]; temas?: string[]; obs?: string; autor?: string };
type Msg = { id: string; data_hora?: string; autor?: string; empresa?: string; rotulo_regra?: string; texto: string };
type Sugestao = { intencao: string; temas: string[]; sinais: string[]; confianca: 'alta' | 'media' | 'baixa'; justificativa: string; modelo: string };
type ItemChat = Msg & { portal: string; processo: string; lotes: number[]; antes: Msg[]; depois: Msg[]; revisao?: Revisao | null; sugestao?: Sugestao | null };
type ItemDecisao = {
  id: string; portal: string; processo: string; tipo?: string; subtipo?: string; documento?: string;
  empresa?: string; recorrente?: string; decisao_regra?: string; categorias_regra: string[]; ementa?: string;
  alertas: string[]; texto: string; lotes?: number[]; lote?: number;
};
type Stats = {
  por_portal: Record<string, { processos: number; mensagens: number; na_fila: number; revisadas: number; a_rever?: number }>;
  decisoes: number; decisoes_revisadas: number; processos?: string[]; divergentes?: number;
};
type Modo = 'fila' | 'rever' | 'divergencias' | 'busca' | 'decisoes';

const API_PADRAO = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
const TECLAS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o'];
const LOTE = 15;
// Agrupamento visual das intenções (a ordem e as teclas continuam as da taxonomia)
const GRUPO: Record<string, string> = {
  pergunta_esclarecimento: 'Dúvidas e pedidos', pedido_prazo: 'Dúvidas e pedidos', envio_documentos: 'Dúvidas e pedidos',
  negociacao_valor: 'Dúvidas e pedidos', desistencia_cancelamento: 'Dúvidas e pedidos',
  contestacao_concorrente: 'Conflito', contestacao_decisao: 'Conflito', reclamacao_procedimento: 'Conflito',
  defesa_propria: 'Conflito', pedido_acesso: 'Conflito', recurso: 'Conflito',
  instrucao_pregoeiro: 'Condução', resposta_esclarecimento: 'Condução', decisao_pregoeiro: 'Condução', agenda_sessao: 'Condução',
  problema_sistema: 'Outros', cortesia: 'Outros', outro: 'Outros',
};

const ler = (k: string, padrao: string) => { try { return localStorage.getItem(k) || padrao; } catch { return padrao; } };
const gravar = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* sem storage: segue */ } };
const hora = (d?: string) => (d || '').replace('T', ' ').slice(0, 16);

const corAutor = (a?: string) =>
  a === 'fornecedor' ? 'bg-amber-50 text-amber-800 border-amber-200'
    : a === 'pregoeiro' ? 'bg-blue-50 text-blue-800 border-blue-200'
      : a === 'sistema' ? 'bg-slate-100 text-slate-600 border-slate-200'
        : 'bg-rose-50 text-rose-700 border-rose-200';

const Linha = React.forwardRef<HTMLDivElement, { m: Msg; destaque?: boolean }>(({ m, destaque }, ref) => (
  <div ref={ref} className={`flex gap-3 px-3 py-2 rounded-lg ${destaque ? 'bg-white border-2 border-indigo-400 shadow-md my-2' : m.autor === 'sistema' ? 'opacity-50' : 'opacity-80'}`}>
    <div className="w-28 shrink-0 text-[11px] font-mono text-slate-400 pt-0.5">{hora(m.data_hora)}</div>
    <div className="flex-1 min-w-0">
      <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
        <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${corAutor(m.autor)}`}>{m.autor || '?'}</span>
        {m.empresa && <span className="text-[11px] font-semibold text-slate-600 truncate">{m.empresa}</span>}
        {m.rotulo_regra && <span className="text-[10px] font-mono text-slate-400">regra: {m.rotulo_regra}</span>}
      </div>
      <p className={`whitespace-pre-wrap break-words ${destaque ? 'text-base leading-relaxed text-slate-900' : 'text-sm text-slate-600'}`}>{m.texto}</p>
    </div>
  </div>
));

const Chip: React.FC<{ ativo: boolean; onClick: () => void; cor: 'sky' | 'amber'; children: React.ReactNode; title?: string }> =
  ({ ativo, onClick, cor, children, title }) => (
    <button onClick={onClick} title={title}
      className={`text-xs px-2 py-1 rounded-full border transition ${ativo
        ? (cor === 'sky' ? 'bg-sky-100 border-sky-400 text-sky-900 font-semibold' : 'bg-amber-100 border-amber-400 text-amber-900 font-semibold')
        : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'}`}>
      {children}
    </button>
  );

export const CuradoriaChat: React.FC = () => {
  const [api, setApi] = useState(() => ler('curadoria.api', API_PADRAO));
  const [revisor, setRevisor] = useState(() => ler('curadoria.revisor', ''));
  const [foco, setFoco] = useState(() => ler('curadoria.foco', '1') === '1');
  const [modo, setModo] = useState<Modo>('fila');
  const [tax, setTax] = useState<Taxonomia | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [processo, setProcesso] = useState('');
  const [autor, setAutor] = useState(() => ler('curadoria.autor', 'fornecedor'));
  const [ordem, setOrdem] = useState('');
  const [busca, setBusca] = useState('');
  const [buscaAplicada, setBuscaAplicada] = useState('');
  const [fila, setFila] = useState<ItemChat[]>([]);
  const [total, setTotal] = useState(0);
  const [pulados, setPulados] = useState(0);
  const [temas, setTemas] = useState<string[]>([]);
  const [marcas, setMarcas] = useState<string[]>([]);
  const [obs, setObs] = useState('');
  const [autorCorrigido, setAutorCorrigido] = useState('');
  const [historico, setHistorico] = useState<{ item: ItemChat; salvo?: Revisao }[]>([]);
  const [sessao, setSessao] = useState(0);
  const [decs, setDecs] = useState<ItemDecisao[]>([]);
  const [totalDec, setTotalDec] = useState(0);
  const [decisao, setDecisao] = useState('');
  const [motivos, setMotivos] = useState<string[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [ajuda, setAjuda] = useState(false);
  const [config, setConfig] = useState(false);
  const alvoRef = useRef<HTMLDivElement>(null);
  const revisorRef = useRef<HTMLInputElement>(null);

  const req = useCallback(async (caminho: string, corpo?: unknown) => {
    const r = await fetch(`${api.replace(/\/$/, '')}/api/curadoria-chat${caminho}`, corpo === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
    });
    if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`);
    return r.json();
  }, [api]);

  const limpar = () => { setMarcas([]); setTemas([]); setObs(''); setAutorCorrigido(''); setDecisao(''); setMotivos([]); };

  const carregar = useCallback(async () => {
    try {
      setErro(null);
      const [t, s] = await Promise.all([req('/taxonomia'), req('/stats')]);
      setTax(t); setStats(s);
      if (modo !== 'decisoes') {
        const q = new URLSearchParams({
          offset: String(pulados), limite: String(LOTE), autor, ordem: modo === 'fila' ? ordem : '', contexto: '6',
          portal: processo.split(':')[0] || '', processo: processo.split(':')[1] || '',
          rever: String(modo === 'rever'), busca: modo === 'busca' ? buscaAplicada : '',
          incluir_revisadas: String(modo === 'busca'), divergentes: String(modo === 'divergencias'),
        });
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
  }, [req, modo, autor, ordem, processo, buscaAplicada, pulados]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { gravar('curadoria.api', api); }, [api]);
  useEffect(() => { gravar('curadoria.revisor', revisor); }, [revisor]);
  useEffect(() => { gravar('curadoria.foco', foco ? '1' : '0'); }, [foco]);
  useEffect(() => { gravar('curadoria.autor', autor); }, [autor]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 3500); return () => clearTimeout(t); }, [toast]);

  const atual = fila[0];
  const decAtual = decs[0];

  // Revisão antiga (ou a que acabou de ser desfeita) preenche sinais, temas e observação; senão, a sugestão do Claude
  useEffect(() => {
    const r = atual?.revisao;
    const sg = atual?.sugestao;
    const rTemas = r?.temas || [], rSinais = r?.sinais || r?.marcas || [];
    // Revisão antiga sem tema/sinal (taxonomia de 2026-10-15 não tinha tema): completa com o que o Claude sugeriu
    setTemas(rTemas.length ? rTemas : (sg?.temas || []));
    setMarcas(rSinais.length ? rSinais : (sg?.sinais || []));
    setObs(r?.obs || '');
    alvoRef.current?.scrollIntoView({ block: 'center' });
  }, [atual?.id]);

  // Intenções do lado de quem escreveu (fornecedor ou pregoeiro); autor indefinido vê todas
  const ladoAtual = autorCorrigido || atual?.revisao?.autor || atual?.autor || '';
  const intencoesVisiveis = useMemo(() => (tax?.intencoes || []).filter(o =>
    !o.lados || !['fornecedor', 'pregoeiro'].includes(ladoAtual) || o.lados.includes(ladoAtual)), [tax, ladoAtual]);
  const grupos = useMemo(() => {
    const g: { nome: string; itens: { o: Opcao; tecla: string }[] }[] = [];
    intencoesVisiveis.forEach((o, i) => {
      const nome = GRUPO[o.id] || 'Outros';
      const ult = g[g.length - 1];
      if (ult && ult.nome === nome) ult.itens.push({ o, tecla: TECLAS[i] });
      else g.push({ nome, itens: [{ o, tecla: TECLAS[i] }] });
    });
    return g;
  }, [intencoesVisiveis]);
  const nomeIntencao = (id?: string) => tax?.intencoes.find(o => o.id === id)?.nome || id || '';

  const avancar = (salvo?: Revisao) => {
    if (atual) setHistorico(h => [...h.slice(-49), { item: atual, salvo }]);
    setFila(f => f.slice(1));
    limpar();
    // Salva some da fila no servidor (recarrega do mesmo ponto); pulada ou busca (inclui revisadas) anda o offset
    if (fila.length <= 2) { if (salvo && modo !== 'busca' && modo !== 'divergencias') carregar(); else setPulados(p => p + LOTE); }
  };

  const salvarChat = useCallback(async (intencao: string) => {
    if (!atual || salvando) return;
    if (!revisor.trim()) { setAviso('Informe seu nome em "Revisor" (canto superior direito) antes de salvar.'); revisorRef.current?.focus(); return; }
    setSalvando(true);
    try {
      const rev = {
        id: atual.id, intencao, temas, sinais: marcas, obs, autor_corrigido: autorCorrigido || null,
        sugestao_intencao: atual.sugestao?.intencao || null, sugestao_modelo: atual.sugestao?.modelo || null,
      };
      await req('/revisar', { revisado_por: revisor, revisoes: [rev] });
      setTotal(t => Math.max(0, t - 1)); setSessao(n => n + 1); setAviso(null);
      setToast(`Salvo: ${nomeIntencao(intencao)}  ·  ← volta para corrigir`);
      avancar({ intencao, temas, sinais: marcas, obs, taxonomia: tax?.versao, autor: autorCorrigido || atual.autor });
    } catch (e: any) { setAviso(`Não salvou: ${e?.message || e}`); } finally { setSalvando(false); }
  }, [atual, salvando, revisor, req, marcas, temas, obs, autorCorrigido, fila.length, carregar, tax]);

  const voltar = () => {
    const ult = historico[historico.length - 1];
    if (!ult) { setToast('Nada para voltar nesta sessão.'); return; }
    setHistorico(h => h.slice(0, -1));
    setFila(f => [{ ...ult.item, revisao: ult.salvo || ult.item.revisao }, ...f]);
    if (ult.salvo) setTotal(t => t + 1);
  };

  const salvarDecisao = useCallback(async () => {
    if (!decAtual || !decisao || salvando) return;
    if (!revisor.trim()) { setAviso('Informe seu nome em "Revisor" antes de salvar.'); revisorRef.current?.focus(); return; }
    setSalvando(true);
    try {
      await req('/revisar-decisao', { revisado_por: revisor, revisoes: [{ id: decAtual.id, decisao, motivos, marcas, obs }] });
      setDecs(d => d.slice(1)); setTotalDec(t => t - 1); limpar(); setAviso(null); setSessao(n => n + 1);
      setToast(`Decisão salva: ${decisao}`);
      if (decs.length <= 2) carregar();
    } catch (e: any) { setAviso(`Não salvou: ${e?.message || e}`); } finally { setSalvando(false); }
  }, [decAtual, decisao, salvando, revisor, req, motivos, marcas, obs, decs.length, carregar]);

  const pular = () => {
    if (modo === 'decisoes') { setDecs(d => d.slice(1)); if (decs.length <= 2) setPulados(p => p + 5); limpar(); }
    else avancar();
  };

  const trocarModo = (m: Modo) => { setModo(m); setPulados(0); setHistorico([]); };

  // Atalhos. Só ficam desligados enquanto se digita (campo de texto); Esc sai do campo.
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      const digitando = alvo && (alvo.tagName === 'TEXTAREA' ||
        (alvo.tagName === 'INPUT' && !['checkbox', 'radio', 'button'].includes((alvo as HTMLInputElement).type)));
      if (e.key === 'Escape') { (document.activeElement as HTMLElement)?.blur(); setAjuda(false); setConfig(false); return; }
      if (digitando || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === '?') { e.preventDefault(); setAjuda(a => !a); return; }
      if (modo === 'decisoes' || !tax) return;
      if (e.shiftKey && /^Digit[1-9]$/.test(e.code)) {  // Shift+1..7 liga/desliga temas
        const t = tax.temas[Number(e.code.slice(5)) - 1];
        if (t) { e.preventDefault(); setTemas(l => l.includes(t.id) ? l.filter(x => x !== t.id) : [...l, t.id]); }
        return;
      }
      if (alvo?.tagName === 'SELECT') return;
      const i = TECLAS.indexOf(e.key.toLowerCase());
      if (i >= 0 && intencoesVisiveis[i]) { e.preventDefault(); salvarChat(intencoesVisiveis[i].id); }
      else if (e.key === 'Enter' && atual?.sugestao) { e.preventDefault(); salvarChat(atual.sugestao.intencao); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); pular(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); voltar(); }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  });

  const alternar = (lista: string[], set: (v: string[]) => void, v: string) =>
    set(lista.includes(v) ? lista.filter(x => x !== v) : [...lista, v]);

  const totais = useMemo(() => Object.values(stats?.por_portal || {}).reduce(
    (a, s) => ({ fila: a.fila + s.na_fila, rev: a.rev + s.revisadas, rever: a.rever + (s.a_rever || 0) }),
    { fila: 0, rev: 0, rever: 0 }), [stats]);
  const pct = totais.fila ? Math.round((100 * totais.rev) / totais.fila) : 0;

  const abas: { id: Modo; rotulo: string; n?: number }[] = [
    { id: 'fila', rotulo: 'Fila', n: totais.fila - totais.rev },
    { id: 'rever', rotulo: 'Revisar de novo', n: totais.rever },
    { id: 'divergencias', rotulo: 'Divergências', n: stats?.divergentes },
    { id: 'busca', rotulo: 'Buscar / corrigir' },
    { id: 'decisoes', rotulo: 'Decisões', n: stats ? stats.decisoes - stats.decisoes_revisadas : undefined },
  ];

  const sel = 'text-xs bg-white border border-slate-200 rounded-lg px-2 py-1.5 outline-none focus:border-indigo-400';

  const conteudo = (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Barra superior: modo, filtros e progresso numa linha */}
      <div className="shrink-0 border-b border-slate-200 bg-white px-4 py-2 flex flex-wrap items-center gap-2">
        <span className="font-extrabold text-slate-900 mr-1">Curadoria</span>
        <div className="flex p-0.5 bg-slate-100 rounded-lg text-xs font-semibold">
          {abas.map(a => (
            <button key={a.id} onClick={() => trocarModo(a.id)}
              className={`px-2.5 py-1 rounded-md ${modo === a.id ? 'bg-white shadow-sm text-slate-900' : 'text-slate-500 hover:text-slate-800'}`}>
              {a.rotulo}{a.n !== undefined && <span className={`ml-1 ${(a.id === 'rever' || a.id === 'divergencias') && a.n ? 'text-amber-600' : 'text-slate-400'}`}>{a.n}</span>}
            </button>
          ))}
        </div>
        {modo !== 'decisoes' && (
          <>
            <select value={processo} onChange={e => { setProcesso(e.target.value); setPulados(0); }} className={sel} title="Processo">
              <option value="">todos os processos</option>
              {(stats?.processos || []).map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={autor} onChange={e => { setAutor(e.target.value); setPulados(0); }} className={sel} title="Autor">
              <option value="">todos os autores</option>
              <option value="fornecedor">fornecedor</option>
              <option value="pregoeiro">pregoeiro</option>
              <option value="indeterminado">indeterminado</option>
            </select>
            {modo === 'fila' && (
              <select value={ordem} onChange={e => { setOrdem(e.target.value); setPulados(0); }} className={sel} title="Ordem">
                <option value="">ordem do chat</option>
                <option value="incerteza">dúvida do Claude primeiro</option>
              </select>
            )}
            {modo === 'busca' && (
              <form onSubmit={e => { e.preventDefault(); setBuscaAplicada(busca.trim()); setPulados(0); }} className="flex items-center gap-1">
                <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg px-2 focus-within:border-indigo-400">
                  <Search className="w-3.5 h-3.5 text-slate-400" />
                  <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="texto da mensagem (Enter)" autoFocus
                    className="text-xs py-1.5 w-52 outline-none" />
                </div>
              </form>
            )}
          </>
        )}
        <div className="ml-auto flex items-center gap-2 text-xs">
          <div className="hidden md:flex items-center gap-2" title="Revisadas na fila (taxonomia atual)">
            <div className="w-24 h-1.5 bg-slate-100 rounded"><div className="h-1.5 bg-emerald-500 rounded" style={{ width: `${pct}%` }} /></div>
            <span className="text-slate-500">{totais.rev}/{totais.fila}</span>
            {sessao > 0 && <span className="text-emerald-700 font-semibold">+{sessao} hoje</span>}
          </div>
          <input ref={revisorRef} value={revisor} onChange={e => setRevisor(e.target.value)} placeholder="Revisor"
            className={`border rounded-lg px-2 py-1.5 w-28 outline-none focus:border-indigo-400 ${revisor.trim() ? 'border-slate-200' : 'border-rose-400 bg-rose-50'}`} />
          <button onClick={carregar} title="Atualizar" className="p-1.5 rounded-lg hover:bg-slate-100"><RefreshCw className="w-4 h-4 text-slate-500" /></button>
          <button onClick={() => setAjuda(true)} title="Atalhos (?)" className="p-1.5 rounded-lg hover:bg-slate-100"><Keyboard className="w-4 h-4 text-slate-500" /></button>
          <div className="relative">
            <button onClick={() => setConfig(c => !c)} title="Configuração" className="p-1.5 rounded-lg hover:bg-slate-100">
              <Settings className={`w-4 h-4 ${erro ? 'text-rose-500' : 'text-slate-500'}`} />
            </button>
            {config && (
              <div className="absolute right-0 top-9 z-20 w-72 rounded-xl border border-slate-200 bg-white shadow-lg p-3 space-y-2">
                <label className="block text-[11px] font-semibold text-slate-500">Endereço da API</label>
                <input value={api} onChange={e => setApi(e.target.value)} className="w-full border border-slate-200 rounded-lg px-2 py-1.5 font-mono text-xs" />
                <p className="text-[11px] text-slate-500">Na pasta src/api: <code>uvicorn main:app --port 8000</code></p>
              </div>
            )}
          </div>
          <button onClick={() => setFoco(f => !f)} title={foco ? 'Sair do modo foco' : 'Modo foco (tela cheia)'} className="p-1.5 rounded-lg hover:bg-slate-100">
            {foco ? <Minimize2 className="w-4 h-4 text-slate-500" /> : <Maximize2 className="w-4 h-4 text-slate-500" />}
          </button>
        </div>
      </div>

      {(erro || aviso) && (
        <div className={`shrink-0 px-4 py-2 text-xs flex items-center gap-2 ${erro ? 'bg-rose-50 text-rose-800' : 'bg-amber-50 text-amber-800'}`}>
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {erro ? <>API fora do ar em <code>{api}</code> ({erro}). Na pasta src/api: <code>uvicorn main:app --port 8000</code>, depois ↻.</> : aviso}
        </div>
      )}

      {/* CHAT */}
      {modo !== 'decisoes' && tax && (atual ? (
        <div className="flex-1 min-h-0 grid lg:grid-cols-[minmax(0,1fr)_400px]">
          <div className="min-h-0 overflow-y-auto px-4 py-3">
            <div className="flex items-center gap-2 pb-2 text-xs text-slate-500 sticky top-0 bg-slate-50/95 backdrop-blur z-10">
              <span className="font-bold uppercase">{atual.portal}</span><ChevronRight className="w-3 h-3" />
              <span className="font-mono">{atual.processo}</span>
              {atual.lotes?.length > 0 && <span>· lote(s) {atual.lotes.join(', ')}</span>}
              <span className="ml-auto">{total} {modo === 'busca' ? 'encontradas' : 'restantes'}</span>
            </div>
            {atual.antes.map(m => <Linha key={m.id} m={m} />)}
            <Linha ref={alvoRef} m={atual} destaque />
            {atual.depois.map(m => <Linha key={m.id} m={m} />)}
          </div>

          <aside className="min-h-0 overflow-y-auto border-l border-slate-200 bg-white px-4 py-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className={`px-1.5 py-0.5 rounded border font-semibold ${corAutor(ladoAtual)}`}>{ladoAtual || '?'}</span>
              {atual.empresa && <span className="font-semibold text-slate-700 truncate max-w-[180px]">{atual.empresa}</span>}
              <select value={autorCorrigido} onChange={e => setAutorCorrigido(e.target.value)} className="ml-auto text-[11px] border border-slate-200 rounded px-1 py-0.5" title="Corrigir autor">
                <option value="">autor ok</option>
                <option value="fornecedor">é fornecedor</option>
                <option value="pregoeiro">é pregoeiro</option>
                <option value="sistema">é sistema</option>
              </select>
            </div>

            {atual.revisao && (
              <div className="text-xs rounded-lg bg-slate-50 border border-slate-200 px-2.5 py-1.5">
                {modo === 'divergencias' ? 'Você classificou: ' : 'Classificação atual: '}<b>{nomeIntencao(atual.revisao.intencao)}</b>
                <span className="text-slate-400"> ({atual.revisao.taxonomia || 'v1'})</span>
              </div>
            )}

            {atual.sugestao && (
              <div className={`rounded-lg border px-2.5 py-2 text-xs ${atual.sugestao.confianca === 'alta' ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : atual.sugestao.confianca === 'media' ? 'bg-sky-50 border-sky-200 text-sky-900' : 'bg-amber-50 border-amber-200 text-amber-900'}`}>
                <div className="font-semibold flex items-center gap-1"><Sparkles className="w-3.5 h-3.5" />
                  {nomeIntencao(atual.sugestao.intencao)} <span className="font-normal">· {atual.sugestao.confianca}</span>
                  <kbd className="ml-auto font-mono px-1 rounded bg-white/80 border text-[10px]">Enter</kbd>
                </div>
                <div className="mt-0.5 opacity-80">{atual.sugestao.justificativa}</div>
                {(atual.sugestao.temas.length > 0 || atual.sugestao.sinais.length > 0) && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1">
                    {atual.sugestao.temas.map(t => <span key={t} className="px-1.5 py-0.5 rounded-full bg-white/80 border border-sky-200 text-sky-800">{tax.temas.find(x => x.id === t)?.nome || t}</span>)}
                    {atual.sugestao.sinais.map(t => <span key={t} className="px-1.5 py-0.5 rounded-full bg-white/80 border border-amber-200 text-amber-800">{tax.sinais.find(x => x.id === t)?.nome || t}</span>)}
                    <button onClick={() => { setTemas(atual.sugestao!.temas); setMarcas(atual.sugestao!.sinais); }}
                      className="ml-auto underline opacity-80 hover:opacity-100" title="Substitui os temas e sinais marcados pelos sugeridos">usar estes</button>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-2">
              {grupos.map(g => (
                <div key={g.nome}>
                  <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">{g.nome}</div>
                  <div className="grid grid-cols-2 gap-1">
                    {g.itens.map(({ o, tecla }) => {
                      const sug = atual.sugestao?.intencao === o.id;
                      const ant = atual.revisao?.intencao === o.id;
                      return (
                        <button key={o.id} onClick={() => salvarChat(o.id)} disabled={salvando} title={o.dica}
                          className={`flex items-center gap-1.5 text-left text-[13px] leading-tight px-2 py-1.5 rounded-lg border disabled:opacity-50 hover:border-indigo-400 hover:bg-indigo-50 ${sug ? 'bg-indigo-50 border-indigo-400 ring-2 ring-indigo-100' : ant ? 'bg-slate-100 border-slate-300' : 'bg-white border-slate-200'}`}>
                          <kbd className="text-[10px] font-mono w-4 text-center rounded bg-slate-100 border border-slate-200 shrink-0">{tecla}</kbd>
                          <span>{o.nome}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Tema <span className="normal-case font-normal">(Shift+1…{tax.temas.length})</span></div>
              <div className="flex flex-wrap gap-1">
                {tax.temas.map((t, i) => (
                  <Chip key={t.id} ativo={temas.includes(t.id)} onClick={() => alternar(temas, setTemas, t.id)} cor="sky" title={`Shift+${i + 1}`}>{t.nome}</Chip>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Sinais</div>
              <div className="flex flex-wrap gap-1">
                {(tax.sinais || tax.marcas).map(m => (
                  <Chip key={m.id} ativo={marcas.includes(m.id)} onClick={() => alternar(marcas, setMarcas, m.id)} cor="amber">
                    {m.id === 'exemplo_ouro' && <Star className="inline w-3 h-3 mr-0.5 -mt-0.5" />}{m.nome}
                  </Chip>
                ))}
              </div>
            </div>
            <textarea value={obs} onChange={e => setObs(e.target.value)} rows={2} placeholder="Observação (opcional) — Esc volta aos atalhos"
              className="w-full text-sm bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-indigo-400" />
            <div className="grid grid-cols-2 gap-2">
              <button onClick={voltar} disabled={!historico.length} className="text-xs px-2 py-1.5 rounded-lg border border-slate-200 bg-white inline-flex items-center justify-center gap-1 disabled:opacity-40">
                <ArrowLeft className="w-3.5 h-3.5" /> Voltar (←)
              </button>
              <button onClick={pular} className="text-xs px-2 py-1.5 rounded-lg border border-slate-200 bg-white inline-flex items-center justify-center gap-1">
                Pular (→) <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </aside>
        </div>
      ) : !erro && (
        <Vazio texto={modo === 'busca' && !buscaAplicada ? 'Digite um trecho da mensagem e aperte Enter (inclui as já revisadas).' : 'Nada pendente com esses filtros.'} />
      ))}

      {/* DECISÕES */}
      {modo === 'decisoes' && tax && (decAtual ? (
        <div className="flex-1 min-h-0 grid lg:grid-cols-[minmax(0,1fr)_400px]">
          <div className="min-h-0 overflow-y-auto px-4 py-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-bold uppercase">{decAtual.portal}</span><ChevronRight className="w-3 h-3" />
              <span className="font-mono">{decAtual.processo}</span>
              <span className="px-1.5 py-0.5 rounded bg-slate-100 font-mono">{decAtual.subtipo || decAtual.tipo}</span>
              {decAtual.decisao_regra && <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 font-semibold">regra: {decAtual.decisao_regra}</span>}
              <span className="ml-auto">{totalDec} restantes</span>
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
            {decAtual.ementa && <p className="text-xs bg-white border border-slate-200 rounded-lg p-2 text-slate-700"><b>Ementa:</b> {decAtual.ementa}</p>}
            <div className="text-sm text-slate-700 whitespace-pre-wrap bg-white border border-slate-200 rounded-lg p-3">{decAtual.texto}</div>
          </div>
          <aside className="min-h-0 overflow-y-auto border-l border-slate-200 bg-white px-4 py-3 space-y-3">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Decisão</div>
              <div className="flex flex-wrap gap-1.5">
                {tax.decisoes.map(d => (
                  <button key={d} onClick={() => setDecisao(d)}
                    className={`text-xs px-2 py-1 rounded-lg border ${decisao === d ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-slate-200 text-slate-700'}`}>{d}</button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Motivos</div>
              <div className="flex flex-wrap gap-1">
                {tax.motivos.map(m => (
                  <Chip key={m} ativo={motivos.includes(m)} onClick={() => alternar(motivos, setMotivos, m)} cor="amber"
                    title={decAtual.categorias_regra.includes(m) ? 'a regra apontou este motivo' : undefined}>
                    {decAtual.categorias_regra.includes(m) ? '• ' : ''}{m}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Sinais</div>
              <div className="flex flex-wrap gap-1">
                {tax.marcas.map(m => (
                  <Chip key={m.id} ativo={marcas.includes(m.id)} onClick={() => alternar(marcas, setMarcas, m.id)} cor="amber">{m.nome}</Chip>
                ))}
              </div>
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
          </aside>
        </div>
      ) : !erro && <Vazio texto="Nenhuma decisão pendente." />)}

      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] rounded-lg bg-slate-900 text-white text-sm px-4 py-2 shadow-lg">{toast}</div>
      )}

      {ajuda && (
        <div className="fixed inset-0 z-[70] bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setAjuda(false)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-5 text-sm" onClick={e => e.stopPropagation()}>
            <div className="font-bold text-slate-900 mb-3 flex items-center gap-2"><Keyboard className="w-4 h-4" /> Atalhos</div>
            <table className="w-full text-left">
              <tbody className="[&_td]:py-1 [&_td:first-child]:pr-4 [&_td:first-child]:font-mono [&_td:first-child]:text-xs">
                <tr><td>1–9, q w e r t…</td><td>salva a intenção da tecla (as teclas mudam conforme o autor)</td></tr>
                <tr><td>Enter</td><td>aceita a sugestão do Claude</td></tr>
                <tr><td>Shift+1…7</td><td>liga/desliga o tema</td></tr>
                <tr><td>←</td><td>volta para a mensagem anterior (corrige o que acabou de salvar)</td></tr>
                <tr><td>→</td><td>pula a mensagem</td></tr>
                <tr><td>Esc</td><td>sai do campo de texto e volta aos atalhos</td></tr>
                <tr><td>?</td><td>abre/fecha esta ajuda</td></tr>
              </tbody>
            </table>
            <p className="text-xs text-slate-500 mt-3">Para corrigir algo antigo: aba <b>Buscar / corrigir</b>, escolha o processo e busque um trecho do texto.</p>
          </div>
        </div>
      )}
    </div>
  );

  return foco
    ? <div className="fixed inset-0 z-50">{conteudo}</div>
    : <div className="h-[calc(100vh-11rem)] min-h-[560px] rounded-2xl border border-slate-200 overflow-hidden">{conteudo}</div>;
};

const Vazio: React.FC<{ texto: string }> = ({ texto }) => (
  <div className="flex-1 flex items-center justify-center p-10">
    <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500 max-w-md">{texto}</div>
  </div>
);
