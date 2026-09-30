import React from 'react';
import { Layers, Play, Settings, Search, Cpu, Sparkles, BookOpen } from 'lucide-react';
import { SectionId } from '../types';

interface NavbarProps {
  activeSection: SectionId;
  onSelectSection: (id: SectionId) => void;
  onOpenSearch: () => void;
  onOpenComponentDetail: (id: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeSection,
  onSelectSection,
  onOpenSearch,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Left: Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center text-white font-black shadow-sm tracking-tight">
            <span className="text-lg">Tu</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-slate-900 tracking-tight">Tunix</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                Tune-in-JAX
              </span>
            </div>
            <p className="text-xs text-slate-500 hidden sm:block">
              Framework Nativo em JAX para Pós-Treinamento de LLMs
            </p>
          </div>
        </div>

        {/* Center: Navigation Shortcuts */}
        <nav className="hidden md:flex items-center space-x-1">
          <button
            onClick={() => onSelectSection('high-level-architecture')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
              activeSection === 'high-level-architecture'
                ? 'bg-blue-50 text-blue-700'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Arquitetura
          </button>
          <button
            onClick={() => onSelectSection('sft')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
              activeSection === 'sft'
                ? 'bg-emerald-50 text-emerald-700'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            Pipeline SFT
          </button>
          <button
            onClick={() => onSelectSection('rl')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
              activeSection === 'rl'
                ? 'bg-purple-50 text-purple-700'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Pipeline RL
          </button>
          <button
            onClick={() => onSelectSection('agentic-rl')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
              activeSection === 'agentic-rl'
                ? 'bg-amber-50 text-amber-700'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            RL Agêntico
          </button>
          <button
            onClick={() => onSelectSection('interactive-simulator')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
              activeSection === 'interactive-simulator'
                ? 'bg-indigo-50 text-indigo-700 font-bold'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Play className="w-3.5 h-3.5 text-indigo-600 fill-indigo-600" />
            Simulador ao Vivo
          </button>
          <button
            onClick={() => onSelectSection('config-explorer')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
              activeSection === 'config-explorer'
                ? 'bg-slate-200 text-slate-900'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            Configurações
          </button>
        </nav>

        {/* Right: Search & Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onOpenSearch}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-500 hover:text-slate-700 text-xs transition-colors shadow-2xs"
            title="Buscar arquitetura e componentes (Cmd+K / Ctrl+K)"
          >
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <span className="hidden sm:inline">Buscar documentação...</span>
            <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono bg-white border border-slate-200 rounded text-slate-400">
              ⌘K
            </kbd>
          </button>
        </div>
      </div>
    </header>
  );
};
