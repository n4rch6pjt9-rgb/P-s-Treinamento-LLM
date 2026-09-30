import React from 'react';
import { X, Code2, Cpu, ArrowDownRight, Copy, Check } from 'lucide-react';
import { SFT_COMPONENTS, RL_COMPONENTS, AGENTIC_COMPONENTS, ARCHITECTURE_LAYERS } from '../data/tunixData';
import { PipelineComponent } from '../types';

interface ComponentDetailModalProps {
  componentId: string | null;
  onClose: () => void;
}

export const ComponentDetailModal: React.FC<ComponentDetailModalProps> = ({
  componentId,
  onClose,
}) => {
  const [copied, setCopied] = React.useState(false);

  if (!componentId) return null;

  // Busca em todos os componentes de pipeline
  const allPipelineComps: PipelineComponent[] = [
    ...SFT_COMPONENTS,
    ...RL_COMPONENTS,
    ...AGENTIC_COMPONENTS,
  ];

  let foundComp = allPipelineComps.find((c) => c.id === componentId);
  let layerComp: any = null;

  if (!foundComp) {
    // Busca nas camadas de arquitetura
    for (const layer of ARCHITECTURE_LAYERS) {
      const match = layer.components.find((c) => c.id === componentId);
      if (match) {
        layerComp = { ...match, layerName: layer.name, layerColor: layer.color };
        break;
      }
    }
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Cabeçalho */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {foundComp?.name || layerComp?.name || 'Especificação do Componente'}
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                {foundComp?.role || layerComp?.tagline || 'Arquitetura do Framework Tunix'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Corpo */}
        <div className="p-6 overflow-y-auto space-y-5 text-slate-700 text-xs leading-relaxed">
          {/* Visão geral */}
          <div>
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 font-mono">
              Descrição & Função
            </h4>
            <p className="text-sm text-slate-700 leading-relaxed">
              {foundComp?.description || layerComp?.details}
            </p>
          </div>

          {/* Entradas & Saídas */}
          {foundComp && (foundComp.inputs || foundComp.outputs) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              {foundComp.inputs && (
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-mono font-bold text-slate-500 uppercase mb-1.5 flex items-center gap-1">
                    <ArrowDownRight className="w-3 h-3 text-blue-500" />
                    Fontes de Entrada (Inputs)
                  </div>
                  <ul className="space-y-1 text-slate-700">
                    {foundComp.inputs.map((inp, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                        <span>{inp}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {foundComp.outputs && (
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-mono font-bold text-slate-500 uppercase mb-1.5 flex items-center gap-1">
                    <ArrowDownRight className="w-3 h-3 text-emerald-500" />
                    Saídas & Artefatos (Outputs)
                  </div>
                  <ul className="space-y-1 text-slate-700">
                    {foundComp.outputs.map((out, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                        <span>{out}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Parâmetros Chave */}
          {foundComp?.keyParams && (
            <div>
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2 font-mono">
                Parâmetros e Hiperparâmetros Principais
              </h4>
              <div className="border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100">
                {foundComp.keyParams.map((param, idx) => (
                  <div key={idx} className="p-2.5 bg-slate-50/50 flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-blue-600">{param.name}</span>
                      <span className="text-[10px] font-mono text-slate-400 bg-white px-1.5 py-0.5 rounded border border-slate-200">
                        {param.type}
                      </span>
                    </div>
                    <span className="text-slate-600 text-right">{param.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tecnologias da Camada */}
          {layerComp?.tech && (
            <div>
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2 font-mono">
                Frameworks e Bibliotecas Subjacentes
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {layerComp.tech.map((t: string, idx: number) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-800 font-mono font-semibold text-xs border border-slate-200"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Trecho de Código */}
          {foundComp?.codeSnippet && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                  <Code2 className="w-3.5 h-3.5 text-blue-500" />
                  Implementação em Código JAX / Tunix
                </div>
                <button
                  onClick={() => handleCopy(foundComp.codeSnippet!)}
                  className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-800 bg-slate-100 px-2 py-0.5 rounded transition-colors"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? 'Copiado!' : 'Copiar'}</span>
                </button>
              </div>
              <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800">
                <code>{foundComp.codeSnippet}</code>
              </pre>
            </div>
          )}
        </div>

        {/* Rodapé */}
        <div className="px-6 py-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Arquitetura do Sistema Tunix (Tune-in-JAX)</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold transition-colors"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
};
