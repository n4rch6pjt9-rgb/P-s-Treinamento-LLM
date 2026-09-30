import React, { useState } from 'react';
import { FileCode, Copy, Check, Sliders, Cpu, Sparkles, Bot } from 'lucide-react';

export const ConfigPlayground: React.FC = () => {
  const [selectedConfig, setSelectedConfig] = useState<'sft' | 'rl_grpo' | 'agentic'>('sft');
  const [copied, setCopied] = useState(false);

  // Parâmetros dinâmicos para demonstração
  const [learningRate, setLearningRate] = useState<string>('2e-5');
  const [seqLength, setSeqLength] = useState<number>(4096);
  const [batchSize, setBatchSize] = useState<number>(8);
  const [tpuTopology, setTpuTopology] = useState<string>('v5p-64');
  const [rolloutEngine, setRolloutEngine] = useState<string>('vllm');

  const getYamlCode = () => {
    if (selectedConfig === 'sft') {
      return `# Configuração de Job de Supervised Fine-Tuning (SFT) no Tunix
# Esquema definido em launching.md#config-explanation

nome_experimento: "gemma-2-9b-sft-ultrachat"
modo_execucao: "sft"

hardware:
  tipo_tpu: "${tpuTopology}"
  formato_malha: [8, 8]  # [data, fsdp]
  precisao: "bfloat16"

modelo:
  id_modelo: "google/gemma-2-9b"
  id_tokenizador: "google/gemma-2-9b"
  checkpointing_gradiente: true
  estrategia_sharding: "fsdp_tp"

dataset:
  tipo_origem: "parquet"
  url_dataset: "gs://tunix-open-datasets/ultrachat_tokenized_v2"
  comprimento_max_sequencia: ${seqLength}
  empacotamento: true  # Empacota sequências para eliminar desperdício de tokens de preenchimento (pad)
  num_workers: 16

treinador:
  tamanho_lote_global: ${batchSize * 8}
  tamanho_lote_por_dispositivo: ${batchSize}
  passos_maximos: 10000
  passos_aquecimento: 200
  taxa_aprendizado: ${learningRate}
  cronograma_lr: "cosine_decay"
  decaimento_peso: 0.01
  corte_norma_gradiente: 1.0

checkpoint:
  mecanismo: "orbax_async"
  intervalo_passos_salvamento: 500
  manter_top_k: 5
  diretorio_saida: "gs://tunix-experiments/checkpoints/gemma-sft-01"

metricas:
  intervalo_passos_registro: 10
  exportar_para: ["tensorboard", "wandb"]
  projeto_wandb: "tunix-pos-treinamento"`;
    }

    if (selectedConfig === 'rl_grpo') {
      return `# Configuração de Job de Reinforcement Learning (GRPO) no Tunix
# Group Relative Policy Optimization com Rollout Assíncrono via vLLM

nome_experimento: "gemma-2-9b-math-grpo"
modo_execucao: "rl"

algoritmo:
  nome: "GRPO"
  geracoes_por_prompt: 8  # Tamanho do grupo G
  taxa_clip: 0.2
  coeficiente_penalidade_kl: 0.04
  modo_sincronizacao: "ASYNC_ROLLOUT"

workers_rollout:
  motor: "${rolloutEngine}"  # "vllm" ou "sglang"
  concorrencia: 16
  tamanho_paralelismo_tensores: 2
  parametros_amostragem:
    temperatura: 0.7
    top_p: 0.95
    max_tokens: 1024

workers_inferencia:
  modelo_recompensa: "google/gemma-2-27b-math-reward"
  tamanho_lote_recompensa: 32
  usar_modelo_referencia: true
  id_modelo_referencia: "google/gemma-2-9b-it"

treinadores:
  modelo_ator: "google/gemma-2-9b-it"
  taxa_aprendizado: 1e-6
  intervalo_passos_sync_pesos: 1  # Sincroniza com vLLM a cada iteração
  malha_tpu: [4, 16]

fila:
  capacidade: 1024
  fator_prebusca: 2`;
    }

    return `# Configuração de Job de RL Agêntico no Tunix
# Interação Multi-Turno com Ferramentas e Sobreposição Assíncrona TPU/IO

nome_experimento: "tunix-agent-code-and-search"
modo_execucao: "agentic_rl"

agente:
  modelo_politica: "google/gemma-2-9b-it"
  turnos_maximos: 12
  prompt_sistema: "Você é um engenheiro de software especialista com acesso a ferramentas em sandbox."

ambiente:
  tipo_sandbox: "docker_microvm"
  ferramentas_permitidas:
    - nome: "python_interpreter"
      tempo_limite_segundos: 15
      limite_memoria_mb: 2048
    - nome: "web_search"
      provedor: "google_search"
      top_k: 5
    - nome: "bash_sandbox"
      chamadas_sistema_restritas: true

pipeline:
  sobreposicao_assincrona: true
  sobrepor_tpu_com_io: true
  amostras_grpo_por_prompt: 4
  funcao_recompensa: "unit_test_evaluator"`;
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getYamlCode());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 bg-slate-100 px-2.5 py-0.5 rounded-full border border-slate-200">
              Especificações YAML / Dataclass
            </span>
            <span className="text-xs text-slate-400">• Consulte launching.md#config-explanation</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mt-1">
            Gerador de Configurações de Experimentos Tunix
          </h3>
        </div>

        {/* Alternador de Configuração */}
        <div className="bg-slate-100 p-1 rounded-xl flex items-center gap-1 text-xs">
          <button
            onClick={() => setSelectedConfig('sft')}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors ${
              selectedConfig === 'sft'
                ? 'bg-white text-emerald-700 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            Config SFT
          </button>
          <button
            onClick={() => setSelectedConfig('rl_grpo')}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors ${
              selectedConfig === 'rl_grpo'
                ? 'bg-white text-purple-700 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Config RL (GRPO)
          </button>
          <button
            onClick={() => setSelectedConfig('agentic')}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors ${
              selectedConfig === 'agentic'
                ? 'bg-white text-amber-700 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Bot className="w-3.5 h-3.5" />
            Config Agêntico
          </button>
        </div>
      </div>

      {/* Grade: Controles ao Vivo & Exibição do Código */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Coluna de Controles */}
        <div className="lg:col-span-4 p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-4">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-800 pb-2 border-b border-slate-200">
            <Sliders className="w-3.5 h-3.5 text-blue-600" />
            Ajustes Interativos de Hiperparâmetros
          </div>

          <div>
            <label className="text-[11px] font-bold text-slate-700 block mb-1">
              Taxa de Aprendizado (AdamW)
            </label>
            <select
              value={learningRate}
              onChange={(e) => setLearningRate(e.target.value)}
              className="w-full text-xs font-mono bg-white border border-slate-200 rounded-lg p-2 text-slate-800"
            >
              <option value="1e-5">1e-5 (Conservador)</option>
              <option value="2e-5">2e-5 (SFT Padrão)</option>
              <option value="5e-5">5e-5 (Taxa Alta)</option>
              <option value="1e-6">1e-6 (Ajuste de Política)</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-bold text-slate-700 block mb-1">
              Comprimento Máximo de Sequência
            </label>
            <select
              value={seqLength}
              onChange={(e) => setSeqLength(Number(e.target.value))}
              className="w-full text-xs font-mono bg-white border border-slate-200 rounded-lg p-2 text-slate-800"
            >
              <option value={2048}>2048 tokens</option>
              <option value={4096}>4096 tokens (Padrão Gemma)</option>
              <option value={8192}>8192 tokens (Contexto Longo)</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-bold text-slate-700 block mb-1">
              Cluster de TPU Alvo
            </label>
            <select
              value={tpuTopology}
              onChange={(e) => setTpuTopology(e.target.value)}
              className="w-full text-xs font-mono bg-white border border-slate-200 rounded-lg p-2 text-slate-800"
            >
              <option value="v5p-64">Fatia de Pod TPU v5p-64</option>
              <option value="v5e-16">Protótipo TPU v5e-16</option>
              <option value="v4-128">Cluster Grande TPU v4-128</option>
            </select>
          </div>

          {selectedConfig === 'rl_grpo' && (
            <div>
              <label className="text-[11px] font-bold text-slate-700 block mb-1">
                Motor de Inferência para Rollout
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <button
                  onClick={() => setRolloutEngine('vllm')}
                  className={`py-1.5 px-2 rounded-lg font-mono font-bold border transition-colors ${
                    rolloutEngine === 'vllm'
                      ? 'bg-purple-50 border-purple-300 text-purple-700'
                      : 'bg-white border-slate-200 text-slate-600'
                  }`}
                >
                  vLLM
                </button>
                <button
                  onClick={() => setRolloutEngine('sglang')}
                  className={`py-1.5 px-2 rounded-lg font-mono font-bold border transition-colors ${
                    rolloutEngine === 'sglang'
                      ? 'bg-purple-50 border-purple-300 text-purple-700'
                      : 'bg-white border-slate-200 text-slate-600'
                  }`}
                >
                  SGLang
                </button>
              </div>
            </div>
          )}

          <div className="pt-2 text-[11px] text-slate-500 leading-relaxed border-t border-slate-200">
            As configurações do Tunix são validadas com verificadores de tipo Pydantic antes do disparo para o cluster.
          </div>
        </div>

        {/* Coluna de Código */}
        <div className="lg:col-span-8 flex flex-col">
          <div className="flex items-center justify-between pb-2 mb-2 text-xs text-slate-500">
            <span className="font-mono flex items-center gap-1.5 text-slate-700 font-semibold">
              <FileCode className="w-4 h-4 text-blue-500" />
              especificacao_job_tunix.yaml
            </span>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copiado' : 'Copiar YAML'}</span>
            </button>
          </div>

          <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800 flex-1 max-h-[480px]">
            <code>{getYamlCode()}</code>
          </pre>
        </div>
      </div>
    </div>
  );
};
