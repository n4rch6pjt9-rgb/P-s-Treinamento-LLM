import React, { useState } from 'react';
import { ArrowRight, Play, RefreshCw, Zap, Server, Database, GitMerge, Cpu, Layers, Activity } from 'lucide-react';

interface RlPipelineDiagramProps {
  onSelectComponent: (componentId: string) => void;
}

export const RlPipelineDiagram: React.FC<RlPipelineDiagramProps> = ({
  onSelectComponent,
}) => {
  const [syncMode, setSyncMode] = useState<'async' | 'sync'>('async');
  const [simStep, setSimStep] = useState<number | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  const runSimulation = () => {
    setIsSimulating(true);
    setSimStep(0);
    // 0: Rollout Workers amostrando
    // 1: Inference Workers avaliando
    // 2: Train Data Queue armazenando no buffer
    // 3: Trainers atualizando Ator/Crítico
    // 4: Weight Sync de volta aos Rollout Workers
    let current = 0;
    const interval = setInterval(() => {
      current++;
      if (current > 4) {
        clearInterval(interval);
        setTimeout(() => {
          setIsSimulating(false);
          setSimStep(null);
        }, 1500);
      } else {
        setSimStep(current);
      }
    }, 1000);
  };

  const isStepActive = (idx: number) => simStep === idx;

  return (
    <div className="my-8 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 sm:p-6 shadow-xs">
      {/* Header & Controles */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-purple-600 bg-purple-50 px-2.5 py-0.5 rounded-full border border-purple-200">
              Pipeline de RL Interativo
            </span>
            <span className="text-xs text-slate-400">• Loop PPO / GRPO</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mt-1">Arquitetura do Loop de Treinamento por Aprendizado por Reforço</h3>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Alternância Síncrono vs Assíncrono */}
          <div className="bg-white border border-slate-200 rounded-lg p-0.5 flex">
            <button
              onClick={() => setSyncMode('async')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
                syncMode === 'async'
                  ? 'bg-purple-50 text-purple-700 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Zap className="w-3 h-3 text-purple-600" />
              Rollout Assíncrono (Alta Vazão)
            </button>
            <button
              onClick={() => setSyncMode('sync')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                syncMode === 'sync'
                  ? 'bg-slate-100 text-slate-900 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Síncrono
            </button>
          </div>

          <button
            onClick={runSimulation}
            disabled={isSimulating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-semibold shadow-xs transition-colors"
          >
            {isSimulating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Simulando Passo {simStep !== null ? simStep + 1 : ''}...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Simular Iteração de RL</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Banner de Modo */}
      <div className="mb-6 p-3 rounded-xl bg-purple-50/70 border border-purple-200 text-xs text-purple-900 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-purple-600 shrink-0" />
          <span>
            <strong>{syncMode === 'async' ? 'Modo de Pipeline Assíncrono:' : 'Modo Síncrono:'}</strong>{' '}
            {syncMode === 'async'
              ? 'Workers de rollout enviam continuamente trajetórias para a fila em memória enquanto os Treinadores calculam gradientes em TPUs, sobrepondo inferência e treino.'
              : 'O Orquestrador pausa os treinadores até que o lote completo de trajetórias seja amostrado e avaliado.'}
          </span>
        </div>
      </div>

      {/* Diagrama Principal */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        {/* Topo: Orquestrador & RL Config */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div
            onClick={() => onSelectComponent('rl-config')}
            className="cursor-pointer rounded-xl border border-slate-200 hover:border-purple-300 p-3.5 bg-slate-50/40 hover:bg-white transition-all flex items-center justify-between"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-bold">
                  CONFIG
                </span>
                <h4 className="text-xs font-bold text-slate-900">Configuração de RL</h4>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Parâmetros PPO/GRPO, penalidade KL, concorrência de rollout, taxas de aprendizado
              </p>
            </div>
            <Layers className="w-4 h-4 text-purple-500" />
          </div>

          <div
            onClick={() => onSelectComponent('rl-orchestrator')}
            className="cursor-pointer rounded-xl border border-slate-200 hover:border-purple-300 p-3.5 bg-slate-50/40 hover:bg-white transition-all flex items-center justify-between"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-bold">
                  ORQUESTRADOR
                </span>
                <h4 className="text-xs font-bold text-slate-900">Orquestrador Global</h4>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Coordena o Controle de Recursos, Registrador de Métricas e o loop algorítmico PPO/GRPO
              </p>
            </div>
            <Activity className="w-4 h-4 text-blue-500" />
          </div>
        </div>

        {/* Grade de Fluxo: Rollout/Inferência à esquerda, Fila no centro, Treinadores à direita */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
          {/* Estágio 1: Workers de Rollout (vLLM / SGLang) */}
          <div className="lg:col-span-4 space-y-4">
            <div
              onClick={() => onSelectComponent('rl-rollout')}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
                isStepActive(0)
                  ? 'ring-2 ring-purple-500 bg-purple-50/70 border-purple-500 shadow-md scale-101'
                  : 'border-slate-200 hover:border-purple-400 bg-white hover:shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                  01 WORKERS DE ROLLOUT
                </span>
                <Server className="w-4 h-4 text-purple-500" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Workers de Rollout (vLLM / SGLang)</h4>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Gera trajetórias de amostra a partir do modelo de política atual usando runtimes em C++ otimizados para geração em lote de alta taxa.
              </p>
              <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-100 text-[11px]">
                <span className="text-slate-400">Runtimes: vLLM, SGLang</span>
                <span className="font-mono text-purple-600 font-semibold">K amostras / prompt</span>
              </div>
            </div>

            {/* Estágio 2: Workers de Inferência (Crítico / Ref / Recompensa) */}
            <div
              onClick={() => onSelectComponent('rl-inference')}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
                isStepActive(1)
                  ? 'ring-2 ring-indigo-500 bg-indigo-50/70 border-indigo-500 shadow-md scale-101'
                  : 'border-slate-200 hover:border-indigo-400 bg-white hover:shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                  02 WORKERS DE INFERÊNCIA
                </span>
                <Cpu className="w-4 h-4 text-indigo-500" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Workers de Inferência</h4>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Hospedam modelos de avaliação (Crítico, Referência, Recompensa). Calculam recompensas escalares, log-probs de referência e valores V(s).
              </p>
              <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-100 text-[11px]">
                <span className="text-slate-400">Modelos: Reward, Ref, Critic</span>
                <span className="font-mono text-indigo-600 font-semibold">Recompensas + LogProbs</span>
              </div>
            </div>
          </div>

          {/* Seta Conectora de Fluxo para a Fila */}
          <div className="lg:col-span-1 flex lg:flex-col items-center justify-center gap-2 py-2">
            <div className="hidden lg:block w-px h-16 bg-slate-200" />
            <div className="p-1.5 rounded-full bg-slate-100 border border-slate-200 text-slate-500">
              <ArrowRight className="w-4 h-4" />
            </div>
            <div className="hidden lg:block w-px h-16 bg-slate-200" />
          </div>

          {/* Estágio 3: Fila de Dados de Treino (Buffer) */}
          <div className="lg:col-span-3 flex flex-col justify-center">
            <div
              onClick={() => onSelectComponent('rl-queue')}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 h-full flex flex-col justify-between ${
                isStepActive(2)
                  ? 'ring-2 ring-emerald-500 bg-emerald-50/70 border-emerald-500 shadow-md scale-101'
                  : 'border-slate-200 hover:border-emerald-400 bg-slate-50/50 hover:bg-white hover:shadow-xs'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                    03 FILA
                  </span>
                  <Database className="w-4 h-4 text-emerald-500" />
                </div>
                <h4 className="text-sm font-bold text-slate-900">Fila de Dados de Treino</h4>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Buffer circular em memória que envia trajetórias avaliadas em fluxo para os Treinadores, desacoplando o rollout dos passos de gradiente.
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-200/80">
                <div className="text-[11px] font-mono text-slate-600 flex items-center justify-between">
                  <span>Capacidade do Buffer</span>
                  <span className="font-bold text-emerald-700">1024 Lotes</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-1.5 mt-1.5 overflow-hidden">
                  <div className="bg-emerald-500 h-full w-3/4 rounded-full" />
                </div>
              </div>
            </div>
          </div>

          {/* Seta Conectora de Fluxo para os Treinadores */}
          <div className="lg:col-span-1 flex lg:flex-col items-center justify-center gap-2 py-2">
            <div className="hidden lg:block w-px h-16 bg-slate-200" />
            <div className="p-1.5 rounded-full bg-slate-100 border border-slate-200 text-slate-500">
              <ArrowRight className="w-4 h-4" />
            </div>
            <div className="hidden lg:block w-px h-16 bg-slate-200" />
          </div>

          {/* Estágio 4: Treinadores (Ator & Crítico) */}
          <div className="lg:col-span-3 flex flex-col justify-center">
            <div
              onClick={() => onSelectComponent('rl-trainers')}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 h-full flex flex-col justify-between ${
                isStepActive(3)
                  ? 'ring-2 ring-blue-500 bg-blue-50/70 border-blue-500 shadow-md scale-101'
                  : 'border-slate-200 hover:border-blue-400 bg-white hover:shadow-xs'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                    04 TREINADORES
                  </span>
                  <Cpu className="w-4 h-4 text-blue-500" />
                </div>
                <h4 className="text-sm font-bold text-slate-900">Treinadores (Ator & Crítico)</h4>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Executa atualizações de parâmetros nas redes do Ator e Crítico através de malhas de TPU multi-dispositivo com objetivo PPO ou perda GRPO.
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] font-mono text-blue-600 flex items-center justify-between">
                <span>Passo JAX JIT</span>
                <span className="font-bold">AdamW / Optax</span>
              </div>
            </div>
          </div>
        </div>

        {/* Estágio 5: Loop de Retorno de Sincronização de Pesos (Banner Inferior) */}
        <div className="mt-6 pt-5 border-t border-slate-200">
          <div
            onClick={() => onSelectComponent('rl-weightsync')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 flex flex-col sm:flex-row items-center justify-between gap-4 ${
              isStepActive(4)
                ? 'ring-2 ring-rose-500 bg-rose-50/70 border-rose-500 shadow-md'
                : 'border-slate-200 hover:border-rose-400 bg-slate-50/40 hover:bg-white'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center shrink-0">
                <GitMerge className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-slate-900">Sincronização de Pesos (Passo 05)</h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold">
                    TRANSMISSÃO DE PARÂMETROS
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Propaga os parâmetros atualizados do modelo Ator dos Treinadores de volta aos Workers de Rollout (vLLM / SGLang) para a próxima iteração.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-3 py-1.5 rounded-lg shrink-0">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-rose-600" />
              <span>Treinadores ➔ Workers de Rollout</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
