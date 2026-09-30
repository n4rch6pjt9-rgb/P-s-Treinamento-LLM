import React from 'react';
import { ListCollapse, ChevronRight, Layers, Cpu, Sparkles, BookOpen, Play, FileCode } from 'lucide-react';
import { SectionId } from '../types';

interface TableOfContentsProps {
  activeSection: SectionId;
  onSelectSection: (id: SectionId) => void;
  inline?: boolean;
}

export const TableOfContents: React.FC<TableOfContentsProps> = ({
  activeSection,
  onSelectSection,
  inline = false,
}) => {
  const sections = [
    {
      id: 'high-level-architecture' as SectionId,
      title: 'Arquitetura de Alto Nível',
      icon: Layers,
      color: 'text-blue-600',
      badge: '5 Camadas',
      subsections: [
        'Camada de Interface do Usuário & Aplicação',
        'Camada de Algoritmos & Fluxos de Trabalho',
        'Camada de Componentes Principais',
        'Camada de Frameworks Fundamentais & Integração',
        'Camada de Hardware',
      ],
    },
    {
      id: 'sft' as SectionId,
      title: 'Supervised Fine-Tuning (SFT)',
      icon: Cpu,
      color: 'text-emerald-600',
      badge: 'Fluxo de Dados & Controle',
      subsections: [
        'Configuração (Config)',
        'Iterator de Dataset',
        'Modelo (nnx.Graph)',
        'Treinador (Trainer)',
        'Otimizador (Optax)',
        'Gerenciador de Checkpoints (Orbax)',
        'Registrador de Métricas (Metrics Logger)',
      ],
    },
    {
      id: 'rl' as SectionId,
      title: 'Reinforcement Learning (RL)',
      icon: Sparkles,
      color: 'text-purple-600',
      badge: 'vLLM / SGLang + JAX',
      subsections: [
        'Configuração de RL (RL Config)',
        'Orquestrador & Controle de Recursos',
        'Workers de Rollout (vLLM / SGLang)',
        'Workers de Inferência (Crítico / Ref / Recompensa)',
        'Fila de Dados de Treino (Train Data Queue)',
        'Treinadores (Ator & Crítico)',
        'Loop de Sincronização de Pesos',
      ],
    },
    {
      id: 'agentic-rl' as SectionId,
      title: 'Reinforcement Learning Agêntico',
      icon: BookOpen,
      color: 'text-amber-600',
      badge: 'Multi-Turno & Ferramentas',
      subsections: [
        'Diálogos Agênticos Multi-Turno',
        'Invocação de Ferramentas & Execução em Sandbox',
        'Rollout & Treinamento Assíncronos',
        'Loteamento & Agrupamento de Trajetórias (GRPO)',
      ],
    },
    {
      id: 'interactive-simulator' as SectionId,
      title: 'Simulador Interativo de Pipeline',
      icon: Play,
      color: 'text-indigo-600',
      badge: 'Execução Passo a Passo',
      subsections: [
        'Simulador de Passo SFT',
        'Simulador de Rollout & Sincronização RL',
        'Loop Multi-Turno Agêntico',
      ],
    },
    {
      id: 'config-explorer' as SectionId,
      title: 'Explorador de Especificações de Config',
      icon: FileCode,
      color: 'text-slate-600',
      badge: 'YAML / Dataclass',
      subsections: [
        'Configuração de Job SFT',
        'Configuração de Job RL / GRPO',
        'Configuração de Ferramentas Agênticas',
      ],
    },
  ];

  if (inline) {
    return (
      <nav aria-label="Sumário interativo" className="my-8 bg-slate-50/80 border border-slate-200/80 rounded-2xl p-6 shadow-2xs">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-700">
              <ListCollapse className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">Índice Analítico</h2>
              <p className="text-xs text-slate-500">Visão Geral da Arquitetura e dos Pipelines do Framework Tunix</p>
            </div>
          </div>
          <span className="text-xs font-mono text-slate-400 bg-white px-2.5 py-1 rounded-md border border-slate-200">
            6 Seções • Interativo
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-5">
          {sections.map((sec, idx) => {
            const Icon = sec.icon;
            const isActive = activeSection === sec.id;
            return (
              <div
                key={sec.id}
                onClick={() => onSelectSection(sec.id)}
                className={`group cursor-pointer rounded-xl p-4 transition-all duration-200 border ${
                  isActive
                    ? 'bg-white border-blue-300 shadow-xs ring-2 ring-blue-500/10'
                    : 'bg-white/60 hover:bg-white border-slate-200/70 hover:border-slate-300 hover:shadow-2xs'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono font-bold text-slate-400">
                      0{idx + 1}
                    </span>
                    <Icon className={`w-4 h-4 ${sec.color}`} />
                    <span className="text-xs font-bold text-slate-800 group-hover:text-blue-600 transition-colors">
                      {sec.title}
                    </span>
                  </div>
                  {sec.badge && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                      {sec.badge}
                    </span>
                  )}
                </div>
                <ul className="space-y-1 pl-7 text-[11px] text-slate-500">
                  {sec.subsections.slice(0, 3).map((sub, i) => (
                    <li key={i} className="flex items-center gap-1.5 truncate">
                      <span className="w-1 h-1 rounded-full bg-slate-300" />
                      <span>{sub}</span>
                    </li>
                  ))}
                  {sec.subsections.length > 3 && (
                    <li className="text-[10px] text-slate-400 pl-2.5">
                      +{sec.subsections.length - 3} tópicos adicionais...
                    </li>
                  )}
                </ul>
              </div>
            );
          })}
        </div>
      </nav>
    );
  }

  // Versão da barra lateral
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 sticky top-20 shadow-2xs">
      <div className="flex items-center gap-2 pb-3 mb-3 border-b border-slate-100 text-xs font-bold uppercase tracking-wider text-slate-500">
        <ListCollapse className="w-3.5 h-3.5 text-slate-400" />
        Conteúdo
      </div>
      <ul className="space-y-1 text-xs">
        {sections.map((sec) => {
          const Icon = sec.icon;
          const isActive = activeSection === sec.id;
          return (
            <li key={sec.id}>
              <button
                onClick={() => onSelectSection(sec.id)}
                className={`w-full text-left px-2.5 py-2 rounded-lg font-medium transition-colors flex items-center justify-between ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                  <span className="truncate">{sec.title}</span>
                </div>
                <ChevronRight className={`w-3 h-3 transition-transform ${isActive ? 'rotate-90 text-blue-500' : 'text-slate-300'}`} />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
};
