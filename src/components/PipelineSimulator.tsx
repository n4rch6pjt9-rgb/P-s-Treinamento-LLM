import React, { useState } from 'react';
import { Play, RotateCcw, Cpu, Sparkles, Bot, Activity, CheckCircle } from 'lucide-react';

export const PipelineSimulator: React.FC = () => {
  const [pipelineMode, setPipelineMode] = useState<'sft' | 'rl' | 'agentic'>('sft');
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [logs, setLogs] = useState<string[]>([
    'Malha de execução JAX Tunix inicializada: (data=8, fsdp=4, tensor=2) em 64x chips TPU v5p.',
  ]);

  const sftSteps = [
    {
      title: 'Streaming de Lote (Dataset Iterator)',
      detail: 'Transmitidas 16 sequências de tokens empacotadas do dataset Parquet. Dimensão do tensor do lote: [16, 4096] bf16.',
      metric: 'Lote: 65.536 tokens',
    },
    {
      title: 'Passada para Frente & Perda (Modelo nnx.Graph)',
      detail: 'Auto-atenção causal executada na malha 2D de TPUs. Perda de entropia cruzada softmax calculada: 1.4182.',
      metric: 'Perda: 1.4182',
    },
    {
      title: 'Passada para Trás (AutoDiff do JAX)',
      detail: '`value_and_grad` do JAX calculou gradientes exatos em todos os 9B de parâmetros particionados. Norma global do gradiente: 0.824.',
      metric: 'Norma Grad: 0.824',
    },
    {
      title: 'Atualização do Otimizador (Optax AdamW)',
      detail: 'Aplicado decaimento de peso (0.01) e taxa de aprendizado com cosseno (1.85e-5). Pesos do modelo atualizados in-place.',
      metric: 'LR: 1.85e-5',
    },
    {
      title: 'Checkpoint Assíncrono (Orbax)',
      detail: 'Disparado salvamento assíncrono em segundo plano para `gs://tunix-checkpoints/gemma-sft/step_1200` via Orbax AsyncCheckpointer.',
      metric: 'Snapshot: OK (GCS)',
    },
    {
      title: 'Exportação de Telemetria (Metrics Logger)',
      detail: 'Emitidas métricas do passo para TensorBoard e W&B. Taxa de transferência do modelo: 28.450 tokens/segundo.',
      metric: '28.4k tok/s',
    },
  ];

  const rlSteps = [
    {
      title: 'Geração de Rollout (vLLM / SGLang)',
      detail: 'Lote de prompts despachado para os workers vLLM. Amostradas K=8 trajetórias por prompt usando Top-P=0.95, Temp=0.7.',
      metric: 'Trajetórias: 64 seqs',
    },
    {
      title: 'Avaliação de Trajetórias (Workers de Inferência)',
      detail: 'Calculadas pontuações do modelo de recompensa (média 0.76) e log-probabilidades do modelo de referência para penalidade KL.',
      metric: 'Recompensa Média: 0.76',
    },
    {
      title: 'Armazenamento em Buffer (Fila de Treino)',
      detail: 'Enfileiradas 64 trajetórias avaliadas no buffer circular assíncrono em memória.',
      metric: 'Fila: 72% ocupada',
    },
    {
      title: 'Atualização de Política & Valor (Treinadores)',
      detail: 'Ator atualizado com perda substituta clipada. Crítico atualizado com perda MSE. Vantagem calculada com GAE.',
      metric: 'Perda Política: -0.042',
    },
    {
      title: 'Transmissão de Sincronização de Pesos',
      detail: 'Sincronizados os pesos atualizados do Ator dos treinadores TPU de volta aos workers de inferência vLLM.',
      metric: 'Latência Sync: 84ms',
    },
  ];

  const agenticSteps = [
    {
      title: 'Deliberação e Pensamento do Agente',
      detail: 'Agente gerou etapa de raciocínio interno: "Preciso verificar o histórico de commits do repositório usando a API do git log."',
      metric: 'Tokens: 48 de pensamento',
    },
    {
      title: 'Invocação de Chamada de Ferramenta',
      detail: 'Agente emitiu invocação de ferramenta: `bash_tool(cmd="git log --oneline -n 3")`. Ambiente recebeu o payload.',
      metric: 'Ação: bash_tool',
    },
    {
      title: 'Execução em Sandbox no Ambiente',
      detail: 'Contêiner Linux em sandbox executou o comando e retornou a observação stdout para a memória da conversa do agente.',
      metric: 'Status: 0 OK',
    },
    {
      title: 'Síntese da Resposta do Agente',
      detail: 'Agente assimilou a observação da ferramenta e formulou a resposta final para a pergunta do usuário.',
      metric: 'Tarefa Concluída',
    },
    {
      title: 'Cálculo de Vantagem em Grupo GRPO',
      detail: 'Calculada a vantagem relativa entre as 8 trajetórias paralelas. Trajetória com alta recompensa impulsionada por vantagem de +1.42.',
      metric: 'Vantagem GRPO: +1.42',
    },
  ];

  const activeSteps =
    pipelineMode === 'sft'
      ? sftSteps
      : pipelineMode === 'rl'
      ? rlSteps
      : agenticSteps;

  const handleNextStep = () => {
    if (currentStep < activeSteps.length - 1) {
      const next = currentStep + 1;
      setCurrentStep(next);
      setLogs((prev) => [
        `[Passo ${next + 1}/${activeSteps.length}] ${activeSteps[next].title} -> ${activeSteps[next].metric}`,
        ...prev.slice(0, 8),
      ]);
    } else {
      setCurrentStep(0);
      setLogs((prev) => [
        `Loop completo de iteração finalizado. Iniciando novo ciclo...`,
        ...prev.slice(0, 8),
      ]);
    }
  };

  const handleAutoRun = () => {
    setIsPlaying(true);
    let step = currentStep;
    const interval = setInterval(() => {
      step = (step + 1) % activeSteps.length;
      setCurrentStep(step);
      setLogs((prev) => [
        `[Auto ${step + 1}/${activeSteps.length}] ${activeSteps[step].title} -> ${activeSteps[step].metric}`,
        ...prev.slice(0, 8),
      ]);
    }, 1200);

    setTimeout(() => {
      clearInterval(interval);
      setIsPlaying(false);
    }, 1200 * activeSteps.length);
  };

  const handleReset = () => {
    setCurrentStep(0);
    setLogs(['Pipeline reiniciado para o passo 0. Pronto para execução.']);
  };

  return (
    <div className="my-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-200">
              Sandbox de Execução Interativa
            </span>
            <span className="text-xs text-slate-400">• Simulador de Treinamento Passo a Passo</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mt-1">
            Simulador de Execução de Pipeline em Tempo Real do Tunix
          </h3>
        </div>

        {/* Seletor de Modo */}
        <div className="bg-slate-100 p-1 rounded-xl flex items-center gap-1 text-xs">
          <button
            onClick={() => {
              setPipelineMode('sft');
              setCurrentStep(0);
            }}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors ${
              pipelineMode === 'sft'
                ? 'bg-white text-emerald-700 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            Loop SFT
          </button>
          <button
            onClick={() => {
              setPipelineMode('rl');
              setCurrentStep(0);
            }}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors ${
              pipelineMode === 'rl'
                ? 'bg-white text-purple-700 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            RL (PPO/GRPO)
          </button>
          <button
            onClick={() => {
              setPipelineMode('agentic');
              setCurrentStep(0);
            }}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors ${
              pipelineMode === 'agentic'
                ? 'bg-white text-amber-700 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Bot className="w-3.5 h-3.5" />
            RL Agêntico
          </button>
        </div>
      </div>

      {/* Progresso dos Passos */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mb-6">
        {activeSteps.map((step, idx) => {
          const isActive = currentStep === idx;
          const isPassed = currentStep > idx;
          return (
            <div
              key={idx}
              onClick={() => setCurrentStep(idx)}
              className={`cursor-pointer p-3 rounded-xl border text-xs transition-all ${
                isActive
                  ? 'border-indigo-500 bg-indigo-50/70 shadow-xs ring-2 ring-indigo-500/20'
                  : isPassed
                  ? 'border-emerald-200 bg-emerald-50/30'
                  : 'border-slate-200 bg-slate-50/50 hover:bg-slate-100'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] font-bold text-slate-400">
                  Passo 0{idx + 1}
                </span>
                {isPassed ? (
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isActive ? 'bg-indigo-600 animate-pulse' : 'bg-slate-300'
                    }`}
                  />
                )}
              </div>
              <p className="font-bold text-slate-800 line-clamp-1">{step.title}</p>
              <p className="text-[10px] font-mono text-indigo-600 mt-1 truncate">
                {step.metric}
              </p>
            </div>
          );
        })}
      </div>

      {/* Detalhes do Passo Ativo & Controles */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Caixa de Destaque */}
        <div className="lg:col-span-2 p-5 rounded-2xl border border-slate-200 bg-slate-50/50 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-bold text-indigo-700 bg-indigo-100 px-2.5 py-0.5 rounded-full">
                Nó Ativo: Passo {currentStep + 1} de {activeSteps.length}
              </span>
              <span className="text-xs font-mono text-slate-500">
                Métrica: <strong className="text-slate-900">{activeSteps[currentStep].metric}</strong>
              </span>
            </div>
            <h4 className="text-base font-bold text-slate-900 mt-2">
              {activeSteps[currentStep].title}
            </h4>
            <p className="text-sm text-slate-600 mt-2 leading-relaxed">
              {activeSteps[currentStep].detail}
            </p>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-200 flex flex-wrap items-center gap-3">
            <button
              onClick={handleNextStep}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-xs transition-colors flex items-center gap-2"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              <span>Avançar Próximo Nó ({currentStep + 1}/{activeSteps.length})</span>
            </button>

            <button
              onClick={handleAutoRun}
              disabled={isPlaying}
              className="px-4 py-2 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-xs shadow-2xs transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <Activity className="w-3.5 h-3.5 text-indigo-600" />
              <span>{isPlaying ? 'Executando Loop...' : 'Executar Ciclo Completo'}</span>
            </button>

            <button
              onClick={handleReset}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors ml-auto"
              title="Reiniciar simulador"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Terminal ao Vivo / Console de Telemetria */}
        <div className="p-4 rounded-2xl bg-slate-950 text-slate-200 font-mono text-xs flex flex-col justify-between border border-slate-800">
          <div>
            <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-800 text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                Telemetria do Cluster Tunix
              </span>
              <span>TPU v5p-64</span>
            </div>
            <div className="space-y-1.5 text-[11px] text-slate-300">
              {logs.map((log, idx) => (
                <div key={idx} className="leading-snug truncate">
                  <span className="text-slate-500 mr-1.5">&gt;</span>
                  {log}
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 mt-3 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400">
            <span>Malha: 2D FSDP+TP</span>
            <span className="text-emerald-400 font-bold">Status: SAUDÁVEL</span>
          </div>
        </div>
      </div>
    </div>
  );
};
