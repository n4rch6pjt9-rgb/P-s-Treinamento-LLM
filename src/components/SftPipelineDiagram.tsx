import React, { useState } from 'react';
import { ArrowRight, Play, RefreshCw, Layers, Database, Cpu, CheckCircle2, ShieldCheck, Activity } from 'lucide-react';

interface SftPipelineDiagramProps {
  onSelectComponent: (componentId: string) => void;
}

export const SftPipelineDiagram: React.FC<SftPipelineDiagramProps> = ({
  onSelectComponent,
}) => {
  const [flowFilter, setFlowFilter] = useState<'all' | 'data' | 'control'>('all');
  const [simStep, setSimStep] = useState<number | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  const runSimulation = () => {
    setIsSimulating(true);
    setSimStep(0);
    const steps = [0, 1, 2, 3, 4, 5, 6];
    let current = 0;
    const interval = setInterval(() => {
      current++;
      if (current >= steps.length) {
        clearInterval(interval);
        setTimeout(() => {
          setIsSimulating(false);
          setSimStep(null);
        }, 1500);
      } else {
        setSimStep(current);
      }
    }, 900);
  };

  const isStepActive = (stepIdx: number) => simStep === stepIdx;

  return (
    <div className="my-8 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 sm:p-6 shadow-xs">
      {/* Header & Controles */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
              Pipeline SFT Interativo
            </span>
            <span className="text-xs text-slate-400">• Fluxo de Dados e Controle</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mt-1">Arquitetura do Pipeline de Supervised Fine-Tuning</h3>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Filtro de tipo de fluxo */}
          <div className="bg-white border border-slate-200 rounded-lg p-0.5 flex">
            <button
              onClick={() => setFlowFilter('all')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                flowFilter === 'all'
                  ? 'bg-emerald-50 text-emerald-700 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Todos os Fluxos
            </button>
            <button
              onClick={() => setFlowFilter('data')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                flowFilter === 'data'
                  ? 'bg-blue-50 text-blue-700 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Fluxo de Dados
            </button>
            <button
              onClick={() => setFlowFilter('control')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                flowFilter === 'control'
                  ? 'bg-purple-50 text-purple-700 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Fluxo de Controle
            </button>
          </div>

          <button
            onClick={runSimulation}
            disabled={isSimulating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold shadow-xs transition-colors"
          >
            {isSimulating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Simulando...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Executar Loop SFT</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Legenda */}
      <div className="flex flex-wrap items-center gap-4 mb-6 text-xs text-slate-500 bg-white p-2.5 rounded-xl border border-slate-200">
        <span className="font-semibold text-slate-700">Legenda:</span>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-blue-500 rounded" />
          <span className="text-blue-700 font-medium">Fluxo de Dados (Tokens / Logits / Tensores)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-purple-500 border-dashed border-t-2 border-purple-500" />
          <span className="text-purple-700 font-medium">Fluxo de Controle (Gradientes / Checkpoints / Métricas)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
          <span className="text-slate-600">Nó de Computação Ativo</span>
        </div>
      </div>

      {/* Esquema do Pipeline */}
      <div className="relative bg-white rounded-2xl border border-slate-200 p-6 overflow-x-auto">
        {/* Nível Superior: Configuração e Fontes Externas */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Caixa de Config */}
          <div
            onClick={() => onSelectComponent('sft-config')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
              isStepActive(0)
                ? 'ring-2 ring-emerald-500 bg-emerald-50/50 border-emerald-500 shadow-md'
                : 'border-slate-200 hover:border-emerald-300 bg-slate-50/50 hover:bg-white'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">
                CONFIG
              </span>
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
            </div>
            <h4 className="text-sm font-bold text-slate-900">Configuração (Config)</h4>
            <p className="text-xs text-slate-500 mt-1">
              URL do dataset, ID do modelo, hiperparâmetros, especificações de checkpoint
            </p>
          </div>

          {/* Dataset de Treino Externo */}
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/30 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-semibold">
                FONTE EXTERNA
              </span>
              <Database className="w-4 h-4 text-blue-600" />
            </div>
            <h4 className="text-sm font-bold text-slate-900">Conjunto de Treinamento</h4>
            <p className="text-xs text-slate-500 mt-1">
              TFDS / Fluxos de tokens em Parquet / Buckets GCS
            </p>
          </div>

          {/* Parâmetros do Modelo Externos */}
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/30 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-semibold">
                PARÂMETROS EXTERNOS
              </span>
              <Layers className="w-4 h-4 text-purple-600" />
            </div>
            <h4 className="text-sm font-bold text-slate-900">Pesos do Modelo</h4>
            <p className="text-xs text-slate-500 mt-1">
              Pesos pré-treinados (Gemma, Llama, Qwen SafeTensors)
            </p>
          </div>
        </div>

        {/* Fluxo Central do Pipeline */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-stretch relative">
          {/* Nó 1: Iterator de Dataset */}
          <div
            onClick={() => onSelectComponent('sft-dataset')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 flex flex-col justify-between ${
              isStepActive(1)
                ? 'ring-2 ring-blue-500 bg-blue-50/50 border-blue-500 shadow-md scale-102'
                : 'border-slate-200 hover:border-blue-400 bg-white hover:shadow-xs'
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                  01 DADOS
                </span>
                <span className="w-2 h-2 rounded-full bg-blue-500" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Iterator de Dataset</h4>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Processa lotes do dataset externo em input_ids e máscaras particionadas.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] font-mono text-blue-600 flex items-center gap-1">
              <span>lote [B, L]</span>
              <ArrowRight className="w-3 h-3 ml-auto" />
            </div>
          </div>

          {/* Nó 2: Modelo (nnx.Graph) */}
          <div
            onClick={() => onSelectComponent('sft-model')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 flex flex-col justify-between ${
              isStepActive(2)
                ? 'ring-2 ring-indigo-500 bg-indigo-50/50 border-indigo-500 shadow-md scale-102'
                : 'border-slate-200 hover:border-indigo-400 bg-white hover:shadow-xs'
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                  02 MODELO
                </span>
                <Cpu className="w-3.5 h-3.5 text-indigo-500" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Modelo (nnx.Graph)</h4>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Inicializado com pesos externos. Executa a passada para frente na malha 2D/3D de TPUs.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] font-mono text-indigo-600 flex items-center gap-1">
              <span>logits [B, L, V]</span>
              <ArrowRight className="w-3 h-3 ml-auto" />
            </div>
          </div>

          {/* Nó 3: Treinador */}
          <div
            onClick={() => onSelectComponent('sft-trainer')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 flex flex-col justify-between ${
              isStepActive(3)
                ? 'ring-2 ring-emerald-500 bg-emerald-50/50 border-emerald-500 shadow-md scale-102'
                : 'border-slate-200 hover:border-emerald-400 bg-white hover:shadow-xs'
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                  03 TREINADOR
                </span>
                <Activity className="w-3.5 h-3.5 text-emerald-500" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Treinador (Trainer)</h4>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Orquestra o passo: chama a função de perda, calcula valores e gradientes via JAX XLA.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] font-mono text-emerald-600 flex items-center gap-1">
              <span>perda & gradientes</span>
              <ArrowRight className="w-3 h-3 ml-auto" />
            </div>
          </div>

          {/* Nó 4: Otimizador (Optax) */}
          <div
            onClick={() => onSelectComponent('sft-optimizer')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 flex flex-col justify-between ${
              isStepActive(4)
                ? 'ring-2 ring-purple-500 bg-purple-50/50 border-purple-500 shadow-md scale-102'
                : 'border-slate-200 hover:border-purple-400 bg-white hover:shadow-xs'
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                  04 OTIMIZADOR
                </span>
                <CheckCircle2 className="w-3.5 h-3.5 text-purple-500" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Otimizador (Optax)</h4>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Aplica atualizações AdamW, cronograma de cosseno e corte de gradiente.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] font-mono text-purple-600 flex items-center gap-1">
              <span>pesos += delta</span>
              <RefreshCw className="w-3 h-3 ml-auto" />
            </div>
          </div>
        </div>

        {/* Nível Inferior: Gerenciador de Checkpoints e Registrador de Métricas */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 pt-6 border-t border-slate-100">
          {/* Gerenciador de Checkpoints (Orbax) */}
          <div
            onClick={() => onSelectComponent('sft-checkpoint')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
              isStepActive(5)
                ? 'ring-2 ring-amber-500 bg-amber-50/50 border-amber-500 shadow-md'
                : 'border-slate-200 hover:border-amber-400 bg-slate-50/50 hover:bg-white'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold">
                PERSISTÊNCIA
              </span>
              <Database className="w-4 h-4 text-amber-600" />
            </div>
            <h4 className="text-sm font-bold text-slate-900">Gerenciador de Checkpoints (Orbax)</h4>
            <p className="text-xs text-slate-500 mt-1">
              Persistência assíncrona periódica de tensores particionados no GCS para recuperação de falhas e inferência.
            </p>
          </div>

          {/* Registrador de Métricas */}
          <div
            onClick={() => onSelectComponent('sft-metrics')}
            className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
              isStepActive(6)
                ? 'ring-2 ring-cyan-500 bg-cyan-50/50 border-cyan-500 shadow-md'
                : 'border-slate-200 hover:border-cyan-400 bg-slate-50/50 hover:bg-white'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-100 text-cyan-800 font-semibold">
                OBSERVABILIDADE
              </span>
              <Activity className="w-4 h-4 text-cyan-600" />
            </div>
            <h4 className="text-sm font-bold text-slate-900">Registrador de Métricas (Metrics Logger)</h4>
            <p className="text-xs text-slate-500 mt-1">
              Exporta perda do passo, taxa de aprendizado, norma do gradiente e tokens/s para TensorBoard/W&B/Cloud.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
