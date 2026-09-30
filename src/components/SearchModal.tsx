import React, { useState, useEffect } from 'react';
import { Search, X, Layers, Cpu, Sparkles, Bot, ChevronRight, Terminal } from 'lucide-react';
import { SFT_COMPONENTS, RL_COMPONENTS, AGENTIC_COMPONENTS, ARCHITECTURE_LAYERS } from '../data/tunixData';
import { SectionId } from '../types';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectComponent: (componentId: string) => void;
  onSelectSection: (sectionId: SectionId) => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({
  isOpen,
  onClose,
  onSelectComponent,
  onSelectSection,
}) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        isOpen ? onClose() : null;
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Itens agregados para busca
  const allItems: {
    id: string;
    title: string;
    subtitle: string;
    type: 'component' | 'section';
    targetId: string;
    sectionId?: SectionId;
    icon: any;
  }[] = [
    {
      id: 'sec-arch',
      title: 'Arquitetura de Alto Nível',
      subtitle: 'Pilha de arquitetura do sistema Tunix em 5 camadas',
      type: 'section',
      targetId: 'high-level-architecture',
      sectionId: 'high-level-architecture',
      icon: Layers,
    },
    {
      id: 'sec-sft',
      title: 'Supervised Fine-Tuning (SFT)',
      subtitle: 'Pipeline com iterator de dataset, modelo, treinador, otimizador e checkpoints',
      type: 'section',
      targetId: 'sft',
      sectionId: 'sft',
      icon: Cpu,
    },
    {
      id: 'sec-rl',
      title: 'Reinforcement Learning (RL)',
      subtitle: 'Workers de rollout (vLLM/SGLang), inferência, fila, treinadores e sincronização de pesos',
      type: 'section',
      targetId: 'rl',
      sectionId: 'rl',
      icon: Sparkles,
    },
    {
      id: 'sec-agentic',
      title: 'Reinforcement Learning Agêntico',
      subtitle: 'Deliberação multi-turno, execução em sandbox de ferramentas, sobreposição assíncrona, GRPO',
      type: 'section',
      targetId: 'agentic-rl',
      sectionId: 'agentic-rl',
      icon: Bot,
    },
    ...SFT_COMPONENTS.map((c) => ({
      id: c.id,
      title: c.name,
      subtitle: `${c.role} • ${c.description.slice(0, 75)}...`,
      type: 'component' as const,
      targetId: c.id,
      icon: Cpu,
    })),
    ...RL_COMPONENTS.map((c) => ({
      id: c.id,
      title: c.name,
      subtitle: `${c.role} • ${c.description.slice(0, 75)}...`,
      type: 'component' as const,
      targetId: c.id,
      icon: Sparkles,
    })),
    ...AGENTIC_COMPONENTS.map((c) => ({
      id: c.id,
      title: c.name,
      subtitle: `${c.role} • ${c.description.slice(0, 75)}...`,
      type: 'component' as const,
      targetId: c.id,
      icon: Bot,
    })),
    ...ARCHITECTURE_LAYERS.flatMap((l) =>
      l.components.map((c) => ({
        id: c.id,
        title: `${c.name} (C${l.number})`,
        subtitle: `${l.name} • ${c.tagline}`,
        type: 'component' as const,
        targetId: c.id,
        icon: Terminal,
      }))
    ),
  ];

  const filtered = query.trim()
    ? allItems.filter(
        (item) =>
          item.title.toLowerCase().includes(query.toLowerCase()) ||
          item.subtitle.toLowerCase().includes(query.toLowerCase())
      )
    : allItems.slice(0, 8);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Campo de Busca */}
        <div className="p-4 border-b border-slate-100 flex items-center gap-3">
          <Search className="w-5 h-5 text-slate-400" />
          <input
            type="text"
            placeholder="Buscar arquitetura Tunix, camadas, componentes, algoritmos..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            className="w-full text-sm text-slate-900 placeholder-slate-400 bg-transparent outline-hidden"
          />
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Lista de Resultados */}
        <div className="p-2 max-h-80 overflow-y-auto divide-y divide-slate-100 text-xs">
          {filtered.length > 0 ? (
            filtered.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    if (item.type === 'section' && item.sectionId) {
                      onSelectSection(item.sectionId);
                    } else {
                      onSelectComponent(item.targetId);
                    }
                    onClose();
                  }}
                  className="p-3 hover:bg-slate-50 rounded-xl cursor-pointer flex items-center justify-between transition-colors group"
                >
                  <div className="flex items-center gap-3 pr-2 truncate">
                    <div className="w-7 h-7 rounded-lg bg-slate-100 group-hover:bg-blue-50 group-hover:text-blue-600 flex items-center justify-center text-slate-500 shrink-0">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="truncate">
                      <div className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                        {item.title}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate">{item.subtitle}</div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-blue-500 shrink-0" />
                </div>
              );
            })
          ) : (
            <div className="p-8 text-center text-slate-400 text-xs">
              Nenhum componente encontrado para &quot;{query}&quot;
            </div>
          )}
        </div>

        {/* Rodapé */}
        <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
          <span>Navegue com o mouse ou teclas direcionais</span>
          <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded font-mono text-[10px]">
            ESC para fechar
          </kbd>
        </div>
      </div>
    </div>
  );
};
