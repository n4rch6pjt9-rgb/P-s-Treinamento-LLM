import React, { useState } from 'react';
import { Play, RefreshCw, Bot, Terminal, Code2, Globe, Database } from 'lucide-react';

interface AgenticRlDiagramProps {
  onSelectComponent: (componentId: string) => void;
}

export const AgenticRlDiagram: React.FC<AgenticRlDiagramProps> = ({
  onSelectComponent,
}) => {
  const [activeTab, setActiveTab] = useState<'loop' | 'async-timeline' | 'grpo-grouping'>('loop');
  const [simTurn, setSimTurn] = useState<number>(0);
  const [isSimulating, setIsSimulating] = useState(false);

  const simulationSteps = [
    {
      turn: 1,
      speaker: 'Prompt do Usuário',
      content: 'Calcule o 50º número de Fibonacci e verifique se ele é primo.',
      type: 'prompt',
    },
    {
      turn: 2,
      speaker: 'Raciocínio do Agente (Thought)',
      content: 'Pensamento: O 50º número de Fibonacci é muito grande (~1.258e10). Devo escrever um script Python para calculá-lo e testar primalidade com Miller-Rabin.',
      type: 'thought',
    },
    {
      turn: 3,
      speaker: 'Chamada de Ferramenta (Ambiente)',
      content: 'python_interpreter(code="def fib(n): ... ; print(fib(50))")',
      type: 'tool_call',
    },
    {
      turn: 4,
      speaker: 'Observação do Ambiente',
      content: 'Stdout: 12586269025 | Composto (divisível por 5, pois termina em 5).',
      type: 'tool_obs',
    },
    {
      turn: 5,
      speaker: 'Resposta Final do Agente',
      content: 'O 50º número de Fibonacci é 12.586.269.025. Ele NÃO é primo (termina em 5, portanto é divisível por 5).',
      type: 'final_response',
    },
  ];

  const handleStepSimulation = () => {
    setIsSimulating(true);
    let step = 0;
    setSimTurn(1);
    const timer = setInterval(() => {
      step++;
      if (step > simulationSteps.length) {
        clearInterval(timer);
        setIsSimulating(false);
      } else {
        setSimTurn(step);
      }
    }, 1100);
  };

  return (
    <div className="my-8 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 sm:p-6 shadow-xs">
      {/* Header & Seletor de Modo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-600 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
              RL Agêntico Interativo
            </span>
            <span className="text-xs text-slate-400">• Raciocínio Multi-Turno & Sandbox de Ferramentas</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mt-1">Arquitetura de Rollout e Treinamento Agente-Ambiente</h3>
        </div>

        {/* Controles de Aba */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="bg-white border border-slate-200 rounded-lg p-0.5 flex">
            <button
              onClick={() => setActiveTab('loop')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                activeTab === 'loop'
                  ? 'bg-amber-50 text-amber-700 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Loop Agente-Ambiente
            </button>
            <button
              onClick={() => setActiveTab('async-timeline')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                activeTab === 'async-timeline'
                  ? 'bg-amber-50 text-amber-700 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Linha do Tempo Assíncrona de TPU
            </button>
            <button
              onClick={() => setActiveTab('grpo-grouping')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                activeTab === 'grpo-grouping'
                  ? 'bg-amber-50 text-amber-700 font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Agrupamento GRPO
            </button>
          </div>
        </div>
      </div>

      {/* ABA 1: Loop Agente <-> Ambiente */}
      {activeTab === 'loop' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
            {/* Esquerda: O Agente (Política do LLM) */}
            <div
              onClick={() => onSelectComponent('agent-core')}
              className="cursor-pointer bg-white rounded-xl border border-slate-200 hover:border-amber-400 p-5 shadow-2xs hover:shadow-xs transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-bold">
                      <Bot className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">Agente (Modelo de Política)</h4>
                      <span className="text-[10px] text-slate-400 font-mono">Gemma-2 / Llama / Qwen</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-700 font-semibold border border-amber-200">
                    nnx.Graph
                  </span>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Realiza raciocínio sequencial em múltiplos turnos. Interpreta o contexto da conversa, decide se dispara uma chamada de ferramenta ou a resposta final, e gerencia sua cadeia de pensamento interna.
                </p>

                <div className="space-y-2">
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] font-mono">
                    <span className="text-amber-700 font-bold">Ação 1:</span> Geração de raciocínio (Thought)
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] font-mono">
                    <span className="text-amber-700 font-bold">Ação 2:</span> Invocação de Ferramenta (Tool Call payload)
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <span>Estado de memória multi-turno</span>
                <span className="text-amber-600 font-mono font-semibold">Máximo de turnos: 8-16</span>
              </div>
            </div>

            {/* Direita: Ambiente e Execução de Ferramentas */}
            <div
              onClick={() => onSelectComponent('agent-env')}
              className="cursor-pointer bg-white rounded-xl border border-slate-200 hover:border-amber-400 p-5 shadow-2xs hover:shadow-xs transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold">
                      <Terminal className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">Ambiente & Sandbox de Ferramentas</h4>
                      <span className="text-[10px] text-slate-400 font-mono">Runtimes de Execução em Sandbox</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200">
                    Host de E/S
                  </span>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Executa as ações solicitadas pelo agente. Isola a execução de forma segura em contêineres ou APIs, captura stdout / retornos JSON e envia as observações de volta ao agente.
                </p>

                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-center">
                    <Code2 className="w-4 h-4 mx-auto text-blue-500 mb-1" />
                    <span className="text-[10px] font-mono font-semibold text-slate-700">Sandbox de Código</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-center">
                    <Globe className="w-4 h-4 mx-auto text-emerald-500 mb-1" />
                    <span className="text-[10px] font-mono font-semibold text-slate-700">Busca na Web</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-center">
                    <Database className="w-4 h-4 mx-auto text-purple-500 mb-1" />
                    <span className="text-[10px] font-mono font-semibold text-slate-700">APIs Customizadas</span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <span>Loop de feedback de observação</span>
                <span className="text-indigo-600 font-mono font-semibold">Execução assíncrona</span>
              </div>
            </div>
          </div>

          {/* Simulador Interativo de Diálogo Multi-Turno */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-800">Inspetor de Trajetória Multi-Turno</span>
                <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
                  Amostra do Loop de Raciocínio
                </span>
              </div>

              <button
                onClick={handleStepSimulation}
                disabled={isSimulating}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                {isSimulating ? (
                  <>
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    <span>Avançando turnos...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3 fill-white" />
                    <span>Reproduzir Rollout Multi-Turno</span>
                  </>
                )}
              </button>
            </div>

            <div className="space-y-3">
              {simulationSteps.map((step, idx) => {
                const isRevealed = simTurn === 0 || simTurn >= step.turn;
                if (!isRevealed) return null;

                const badgeColors: Record<string, string> = {
                  prompt: 'bg-blue-50 text-blue-700 border-blue-200',
                  thought: 'bg-amber-50 text-amber-700 border-amber-200',
                  tool_call: 'bg-purple-50 text-purple-700 border-purple-200',
                  tool_obs: 'bg-emerald-50 text-emerald-700 border-emerald-200',
                  final_response: 'bg-slate-900 text-white border-slate-900',
                };

                return (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-start justify-between gap-2"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${badgeColors[step.type]}`}>
                          {step.speaker}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">Turno {step.turn}</span>
                      </div>
                      <p className="text-xs text-slate-800 font-mono pl-1 pt-1">
                        {step.content}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ABA 2: Linha do Tempo Assíncrona de TPU & E/S */}
      {activeTab === 'async-timeline' && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h4 className="text-sm font-bold text-slate-900">Pipeline Assíncrono & Utilização do Hardware</h4>
              <p className="text-xs text-slate-500 mt-0.5">
                Sobrepor a latência de inferência, a execução de ferramentas em E/S e os cálculos de recompensa elimina bolhas ociosas de TPU.
              </p>
            </div>
            <span className="text-xs font-mono font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200">
              Zero Bolhas de TPU
            </span>
          </div>

          {/* Visualização da Linha do Tempo */}
          <div className="space-y-3 pt-2 text-xs font-mono">
            {/* Trilha 1: Computação em TPU */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-800 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  Workers de Computação em TPU (Inferência de Política & Gradientes)
                </span>
                <span className="text-[10px] text-slate-400">100% Ativo</span>
              </div>
              <div className="grid grid-cols-6 gap-1 text-[10px] text-center font-semibold text-white">
                <div className="bg-blue-600 py-1.5 rounded">Inferência Traj 1</div>
                <div className="bg-blue-500 py-1.5 rounded">Inferência Traj 2</div>
                <div className="bg-indigo-600 py-1.5 rounded">Inferência Traj 3</div>
                <div className="bg-blue-600 py-1.5 rounded">Traj 1 Turno 2</div>
                <div className="bg-blue-500 py-1.5 rounded">Traj 2 Turno 2</div>
                <div className="bg-emerald-600 py-1.5 rounded">Passo PPO/GRPO</div>
              </div>
            </div>

            {/* Trilha 2: E/S e Execução de Ferramentas */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-800 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  Ambiente Host & Execução de Ferramentas (Código / Busca / APIs)
                </span>
                <span className="text-[10px] text-slate-400">E/S Sobreposta</span>
              </div>
              <div className="grid grid-cols-6 gap-1 text-[10px] text-center font-semibold text-white">
                <div className="bg-slate-300 text-slate-600 py-1.5 rounded">Ocioso</div>
                <div className="bg-amber-600 py-1.5 rounded">Sandbox Traj 1</div>
                <div className="bg-amber-500 py-1.5 rounded">Busca Web Traj 2</div>
                <div className="bg-purple-600 py-1.5 rounded">Exec Código Traj 3</div>
                <div className="bg-amber-600 py-1.5 rounded">Ferramenta 2 Traj 1</div>
                <div className="bg-slate-300 text-slate-600 py-1.5 rounded">Prefetch</div>
              </div>
            </div>

            {/* Trilha 3: Avaliador de Recompensas */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-800 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  Avaliação de Recompensas (Verificador / Desfecho / LLM-Juiz)
                </span>
                <span className="text-[10px] text-slate-400">Pontuação Assíncrona</span>
              </div>
              <div className="grid grid-cols-6 gap-1 text-[10px] text-center font-semibold text-white">
                <div className="bg-slate-300 text-slate-600 py-1.5 rounded">Ocioso</div>
                <div className="bg-slate-300 text-slate-600 py-1.5 rounded">Ocioso</div>
                <div className="bg-slate-300 text-slate-600 py-1.5 rounded">Ocioso</div>
                <div className="bg-emerald-600 py-1.5 rounded">Recompensa Traj 1</div>
                <div className="bg-emerald-500 py-1.5 rounded">Recompensa Traj 2</div>
                <div className="bg-emerald-600 py-1.5 rounded">Recompensa Traj 3</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ABA 3: Agrupamento de Trajetórias GRPO */}
      {activeTab === 'grpo-grouping' && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h4 className="text-sm font-bold text-slate-900">Loteamento & Agrupamento de Trajetórias (GRPO)</h4>
              <p className="text-xs text-slate-500 mt-0.5">
                Amostra múltiplas trajetórias completas $G=4$ por prompt, calculando as vantagens em relação à média do grupo para eliminar a necessidade de um modelo de crítico separado.
              </p>
            </div>
            <span className="text-xs font-mono font-bold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md border border-indigo-200">
              Group Relative Policy Optimization
            </span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs">
            <div className="text-slate-400 mb-2"># Fórmula de Normalização de Vantagem:</div>
            <div className="text-emerald-400 text-sm font-bold">
              Vantagem(i) = [ Recompensa(i) - Media(Recompensas_grupo) ] / [ DesvioPadrao(Recompensas_grupo) + 1e-8 ]
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-lg border border-emerald-300 bg-emerald-50/50">
              <div className="flex justify-between font-bold text-slate-900 mb-1">
                <span>Amostra 1</span>
                <span className="text-emerald-600">Recompensa: 1.0</span>
              </div>
              <p className="text-[11px] text-slate-600">Tarefa resolvida com 2 chamadas de ferramenta</p>
              <div className="mt-2 text-xs font-mono text-emerald-700 font-bold">
                Vantagem: +1.26
              </div>
            </div>

            <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/30">
              <div className="flex justify-between font-bold text-slate-900 mb-1">
                <span>Amostra 2</span>
                <span className="text-emerald-600">Recompensa: 0.8</span>
              </div>
              <p className="text-[11px] text-slate-600">Tarefa resolvida com 4 chamadas de ferramenta</p>
              <div className="mt-2 text-xs font-mono text-emerald-700 font-bold">
                Vantagem: +0.63
              </div>
            </div>

            <div className="p-3 rounded-lg border border-rose-200 bg-rose-50/30">
              <div className="flex justify-between font-bold text-slate-900 mb-1">
                <span>Amostra 3</span>
                <span className="text-rose-600">Recompensa: 0.2</span>
              </div>
              <p className="text-[11px] text-slate-600">Erro de sintaxe no bloco de código</p>
              <div className="mt-2 text-xs font-mono text-rose-700 font-bold">
                Vantagem: -1.26
              </div>
            </div>

            <div className="p-3 rounded-lg border border-rose-200 bg-rose-50/30">
              <div className="flex justify-between font-bold text-slate-900 mb-1">
                <span>Amostra 4</span>
                <span className="text-rose-600">Recompensa: 0.4</span>
              </div>
              <p className="text-[11px] text-slate-600">Ultrapassou limite máximo de turnos</p>
              <div className="mt-2 text-xs font-mono text-rose-700 font-bold">
                Vantagem: -0.63
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
