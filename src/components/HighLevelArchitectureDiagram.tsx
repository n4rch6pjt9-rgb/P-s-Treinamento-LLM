import React, { useState } from 'react';
import { ARCHITECTURE_LAYERS } from '../data/tunixData';
import { Cpu, Layers, Terminal, Sparkles, Database, ChevronDown, ChevronUp, Info, ExternalLink } from 'lucide-react';

interface HighLevelArchitectureDiagramProps {
  onSelectComponent: (componentId: string) => void;
}

export const HighLevelArchitectureDiagram: React.FC<HighLevelArchitectureDiagramProps> = ({
  onSelectComponent,
}) => {
  const [expandedLayers, setExpandedLayers] = useState<Record<string, boolean>>({
    'ui-app': true,
    'algo-workflow': true,
    'core-components': true,
    'foundation-frameworks': true,
    'hardware-layer': true,
  });

  const toggleLayer = (layerId: string) => {
    setExpandedLayers((prev) => ({ ...prev, [layerId]: !prev[layerId] }));
  };

  const layerIcons: Record<string, React.ElementType> = {
    'ui-app': Terminal,
    'algo-workflow': Sparkles,
    'core-components': Layers,
    'foundation-frameworks': Database,
    'hardware-layer': Cpu,
  };

  return (
    <div className="my-8 rounded-2xl border border-slate-200 bg-slate-50/50 p-4 sm:p-6 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-blue-600 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
              Esquema Interativo
            </span>
            <span className="text-xs text-slate-400">• Clique nos componentes para ver as especificações JAX</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mt-1">Arquitetura em Camadas do Sistema Tunix</h3>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={() =>
              setExpandedLayers({
                'ui-app': true,
                'algo-workflow': true,
                'core-components': true,
                'foundation-frameworks': true,
                'hardware-layer': true,
              })
            }
            className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-slate-900 font-medium hover:bg-slate-50 transition-colors"
          >
            Expandir Tudo
          </button>
          <button
            onClick={() => setExpandedLayers({})}
            className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-slate-900 font-medium hover:bg-slate-50 transition-colors"
          >
            Recolher
          </button>
        </div>
      </div>

      {/* Pilha de Camadas */}
      <div className="space-y-4">
        {ARCHITECTURE_LAYERS.map((layer, index) => {
          const Icon = layerIcons[layer.id] || Layers;
          const isExpanded = !!expandedLayers[layer.id];

          return (
            <div
              key={layer.id}
              className={`rounded-xl border transition-all duration-200 bg-white overflow-hidden ${
                isExpanded ? 'shadow-xs border-slate-300' : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              {/* Cabeçalho da Camada */}
              <div
                onClick={() => toggleLayer(layer.id)}
                className="cursor-pointer px-4 sm:px-5 py-3.5 flex items-center justify-between bg-white hover:bg-slate-50/80 transition-colors select-none"
              >
                <div className="flex items-center gap-3">
                  <span
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold text-white shadow-2xs"
                    style={{ backgroundColor: layer.color }}
                  >
                    C{layer.number}
                  </span>
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-slate-500" />
                    <h4 className="text-sm font-bold text-slate-900">{layer.name}</h4>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="hidden sm:inline text-xs text-slate-400">
                    {layer.components.length} componentes
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              </div>

              {/* Corpo da Camada */}
              {isExpanded && (
                <div className="px-4 sm:px-5 pb-5 pt-1 border-t border-slate-100 bg-slate-50/40">
                  <p className="text-xs text-slate-600 mb-3.5 leading-relaxed">
                    {layer.description}
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {layer.components.map((comp) => (
                      <div
                        key={comp.id}
                        onClick={() => onSelectComponent(comp.id)}
                        className="group cursor-pointer rounded-xl p-3.5 bg-white border border-slate-200 hover:border-blue-400 hover:shadow-xs transition-all flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <h5 className="text-xs font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                              {comp.name}
                            </h5>
                            <Info className="w-3.5 h-3.5 text-slate-300 group-hover:text-blue-500 transition-colors" />
                          </div>
                          <p className="text-[11px] font-medium text-slate-500 mb-2 line-clamp-1">
                            {comp.tagline}
                          </p>
                          <p className="text-[11px] text-slate-600 leading-snug line-clamp-2 mb-3">
                            {comp.details}
                          </p>
                        </div>

                        <div>
                          {comp.tech && comp.tech.length > 0 && (
                            <div className="flex flex-wrap gap-1 mb-2">
                              {comp.tech.map((t, idx) => (
                                <span
                                  key={idx}
                                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200"
                                >
                                  {t}
                                </span>
                              ))}
                            </div>
                          )}

                          {comp.docsRef && (
                            <div className="text-[10px] font-semibold text-blue-600 flex items-center gap-1 group-hover:underline">
                              <span>Ver {comp.docsRef}</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Indicador de Barramento Inter-camadas */}
              {index < ARCHITECTURE_LAYERS.length - 1 && isExpanded && (
                <div className="flex justify-center -mb-2 py-1 relative z-10">
                  <div className="w-2 h-2 bg-slate-300 rotate-45" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
