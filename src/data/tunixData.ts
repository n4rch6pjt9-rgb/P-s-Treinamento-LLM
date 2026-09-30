import { ArchitectureLayer, PipelineComponent } from '../types';

export const TUNIX_DOCUMENTATION = {
  title: 'Visão Geral do Design',
  subtitle: 'Tunix (Tune-in-JAX)',
  frameworkTagline: 'Framework nativo em JAX para pós-treinamento de grandes modelos de linguagem (LLMs)',
  introParagraph:
    'Este documento fornece uma visão geral do Tunix (Tune-in-JAX), um framework nativo em JAX para pós-treinamento de grandes modelos de linguagem (LLMs). Ele cobre a arquitetura geral em camadas e as arquiteturas de loop de treinamento para Supervised Fine-Tuning (SFT), Reinforcement Learning (RL) e RL Agêntico. Compreender este design ajudará você a utilizar e estender o Tunix de forma eficaz para o ajuste de modelos.',
};

export const ARCHITECTURE_LAYERS: ArchitectureLayer[] = [
  {
    id: 'ui-app',
    number: 1,
    name: 'Camada de Interface do Usuário & Aplicação',
    description:
      'Esta camada superior fornece os pontos de acesso primários para os usuários por meio de ferramentas CLI, cadernos interativos e arquivos de configuração para definir e gerenciar experimentos de ajuste.',
    color: '#3b82f6',
    bgLight: 'bg-blue-50',
    borderColor: 'border-blue-200',
    components: [
      {
        id: 'cli-tools',
        name: 'Tunix CLI & Executor de Jobs',
        tagline: 'Ponto de entrada para execução distribuída em clusters',
        details:
          'Ferramentas de linha de comando que interpretam especificações de treino, gerenciam a inicialização de fatias de TPU multi-host e disparam cargas de treinamento remotas no SLURM ou Vertex AI.',
        tech: ['argparse', 'Click', 'Parser de Config YAML'],
        docsRef: 'launching.md',
      },
      {
        id: 'interactive-notebooks',
        name: 'Notebooks Interativos',
        tagline: 'Ambientes de exploração no Colab Enterprise & Jupyter',
        details:
          'Superfícies de prototipagem para avaliação interativa de modelos, depuração em dispositivo único, varredura rápida de hiperparâmetros e visualização de trajetórias.',
        tech: ['Jupyter', 'Colab TPU v5e', 'IPython'],
        docsRef: 'launching.md',
      },
      {
        id: 'config-specs',
        name: 'Gerenciador de Configurações',
        tagline: 'Definições declarativas de experimentos em YAML / Dataclass',
        details:
          'Sistema de configuração fortemente tipado que define pesos do modelo, fluxos de dados, hiperparâmetros do otimizador, malhas de sharding e frequência de checkpoints.',
        tech: ['Pydantic', 'Python Dataclasses', 'Orbax Config'],
        docsRef: 'launching.md#config-explanation',
      },
    ],
  },
  {
    id: 'algo-workflow',
    number: 2,
    name: 'Camada de Algoritmos & Fluxos de Trabalho',
    description:
      'Esta camada abriga os paradigmas centrais de treinamento, incluindo ajuste fino supervisionado (SFT), aprendizado por reforço (RL) e fluxos agênticos, suportando diversas estratégias de otimização de modelos.',
    color: '#8b5cf6',
    bgLight: 'bg-purple-50',
    borderColor: 'border-purple-200',
    components: [
      {
        id: 'sft-algo',
        name: 'Supervised Fine-Tuning (SFT)',
        tagline: 'Predição de próximo token e alinhamento de instruções',
        details:
          'Pipelines de ajuste fino de parâmetros completos e eficientes (LoRA) otimizados para sequências de contexto longo com empacotamento de sequências (packed sequences).',
        tech: ['Packed Sequences', 'Cross-Entropy Loss', 'FlashAttention-2 / RingAttention'],
        docsRef: 'algorithms.md#sft',
      },
      {
        id: 'rl-algo',
        name: 'Reinforcement Learning (RL)',
        tagline: 'Otimização de política com PPO, GRPO e DPO',
        details:
          'Mecanismos de treinamento de gradiente de política que coordenam rollouts de política, penalidades KL de referência, estimativa de valor e cálculo de vantagem.',
        tech: ['PPO', 'GRPO', 'DPO', 'GAE (Generalized Advantage)'],
        docsRef: 'algorithms.md#rl',
      },
      {
        id: 'agentic-algo',
        name: 'Fluxos de Trabalho Agênticos',
        tagline: 'Raciocínio multi-turno e treino com invocação de ferramentas',
        details:
          'Orquestra a coleta de trajetórias agênticas em múltiplas etapas com sandbox de execução de código externo, consulta à web e loteamento assíncrono de trajetórias.',
        tech: ['Sandbox de Ferramentas', 'Rollout Multi-Turno', 'Agrupamento GRPO'],
        docsRef: 'algorithms.md#agentic',
      },
    ],
  },
  {
    id: 'core-components',
    number: 3,
    name: 'Camada de Componentes Principais',
    description:
      'Responsável pelo funcionamento interno do sistema, esta camada gerencia a orquestração do loop de treinamento, o rastreamento de métricas e o gerenciamento de estado distribuído complexo necessário para execuções em larga escala.',
    color: '#10b981',
    bgLight: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    components: [
      {
        id: 'orchestrator-core',
        name: 'Orquestrador do Loop de Treinamento',
        tagline: 'Coordena ingestão de dados, passos de cálculo e sincronização',
        details:
          'Gerencia a sincronização multi-host, cadência de passos, ciclos de acumulação de gradientes e transferências assíncronas entre workers de rollout e treinadores.',
        tech: ['jax.experimental.multihost', 'Async Queue', 'Resource Barrier'],
      },
      {
        id: 'dist-state',
        name: 'Gerenciador de Estado Distribuído',
        tagline: 'Parâmetros e estados do otimizador particionados (sharded)',
        details:
          'Coordena o particionamento em malhas 2D/3D de dispositivos (Paralelismo de Dados, Paralelismo de Tensores, Paralelismo de Pipeline, FSDP).',
        tech: ['jax.sharding.NamedSharding', 'Mesh', 'PartitionSpec (P)'],
      },
      {
        id: 'metrics-core',
        name: 'Rastreamento de Métricas & Telemetria',
        tagline: 'Throughput em tempo real, perda (loss), norma do gradiente e recompensas',
        details:
          'Coleta de métricas assíncrona com overhead zero, exportando estatísticas de treinamento para TensorBoard, Weights & Biases e Cloud Logging.',
        tech: ['TensorBoard', 'W&B', 'Cloud Monitoring'],
        docsRef: 'metrics.md',
      },
      {
        id: 'checkpoint-core',
        name: 'Mecanismo de Checkpoint Orbax',
        tagline: 'Persistência assíncrona de tensores particionados',
        details:
          'Salvamento não bloqueante de checkpoints diretamente em buckets do Google Cloud Storage (GCS) usando Orbax para recuperação instantânea contra preempção.',
        tech: ['Orbax AsyncCheckpointer', 'TensorStore', 'GCS'],
      },
    ],
  },
  {
    id: 'foundation-frameworks',
    number: 4,
    name: 'Camada de Frameworks Fundamentais & Integração',
    description:
      'Esta camada integra bibliotecas subjacentes de alto desempenho como JAX, Flax e Optax para fornecer computação acelerada, primitivas de redes neurais e otimização eficiente de gradientes.',
    color: '#f59e0b',
    bgLight: 'bg-amber-50',
    borderColor: 'border-amber-200',
    components: [
      {
        id: 'jax-framework',
        name: 'JAX (Compilador XLA)',
        tagline: 'Transformações funcionais combináveis e compilação XLA',
        details:
          'Computação funcional pura, diferenciação automática (grad, vjp), compilação just-in-time (jax.jit) e vetorização paralela (vmap, pmap).',
        tech: ['jax.jit', 'jax.grad', 'jax.lax', 'OpenXLA'],
      },
      {
        id: 'flax-nnx',
        name: 'Flax (nnx.Graph)',
        tagline: 'Abstrações modernas de redes neurais orientadas a objetos',
        details:
          'Flax NNX fornece arquiteturas modulares baseadas em classes Python com gerenciamento de estado explícito, ideal para modelos dinâmicos de LLM.',
        tech: ['flax.nnx', 'nnx.Param', 'nnx.split / nnx.merge'],
        docsRef: 'models.md',
      },
      {
        id: 'optax-framework',
        name: 'Optax',
        tagline: 'Processamento e otimização combinável de gradientes',
        details:
          'Transformações de otimizadores de ponta: AdamW com decaimento de cosseno e aquecimento (warmup), corte de gradientes (clipping) e estados particionados.',
        tech: ['optax.adamw', 'optax.clip_by_global_norm', 'optax.chain'],
      },
      {
        id: 'orbax-framework',
        name: 'Orbax & TensorStore',
        tagline: 'Checkpointing de arrays particionados de alta vazão',
        details:
          'Armazenamento distribuído de arrays com E/S em blocos assíncrona, projetado especificamente para pesos de modelos de vários terabytes em centenas de nós TPU.',
        tech: ['orbax.checkpoint', 'TensorStore', 'zarr'],
      },
    ],
  },
  {
    id: 'hardware-layer',
    number: 5,
    name: 'Camada de Hardware',
    description:
      'A base da pilha gerencia os recursos de computação físicos ou virtuais, especificamente otimizados para Google Cloud TPUs, clusters multi-host de GPU e hosts de CPU.',
    color: '#ef4444',
    bgLight: 'bg-rose-50',
    borderColor: 'border-rose-200',
    components: [
      {
        id: 'google-tpu',
        name: 'Google Cloud TPUs',
        tagline: 'Pods e fatias de TPU v4, v5e, v5p e v6e',
        details:
          'Interconexões ópticas chaveadas (OCS torus) que fornecem largura de banda entre nós de petabits/s para treinamento massivo com escalabilidade quase linear.',
        tech: ['TPU v5p (459 TFLOPS bf16)', 'TPU v5e', 'Chaveador Óptico de Interconexão'],
      },
      {
        id: 'gpu-clusters',
        name: 'Clusters Multi-Host de GPU',
        tagline: 'Clusters NVIDIA H100, H200 e A100 SXM',
        details:
          'Suporta clusters padrão RoCEv2 e InfiniBand via backend JAX CUDA/NCCL com coordenação distribuída entre múltiplos nós.',
        tech: ['NVIDIA H100 NVLink', 'InfiniBand / NCCL', 'CUDA 12+'],
      },
      {
        id: 'cpu-hosts',
        name: 'Sistemas de Computação Host & Armazenamento',
        tagline: 'Nós de alta memória & armazenamento persistente GCS',
        details:
          'Nós de CPU multi-core gerenciando decodificação assíncrona de datasets, pipelines de tokenização, streaming TFDS e sockets para motores de rollout.',
        tech: ['Interconexão gRPC', 'Discos Persistentes GCS', 'VMs de Alta Memória'],
      },
    ],
  },
];

export const SFT_COMPONENTS: PipelineComponent[] = [
  {
    id: 'sft-config',
    name: 'Configuração (Config)',
    role: 'Especificação Central',
    category: 'compute',
    description:
      'Gerencia as configurações de todos os componentes do pipeline, como detalhes do conjunto de dados (ex.: URL), especificações do modelo (ex.: URL, tokenizador), parâmetros do treinador (ex.: passos máximos, hiperparâmetros) e frequência de checkpoints.',
    keyParams: [
      { name: 'dataset_path', type: 'str', desc: 'URL de origem do dataset ou caminho local' },
      { name: 'learning_rate', type: 'float', desc: 'Taxa de aprendizado de pico para AdamW (ex.: 2e-5)' },
      { name: 'max_seq_length', type: 'int', desc: 'Comprimento máximo de sequência (ex.: 4096 / 8192)' },
      { name: 'checkpoint_every_n_steps', type: 'int', desc: 'Frequência de instantâneos Orbax' },
    ],
    codeSnippet: `config = SftConfig(
  model_id="google/gemma-2-9b",
  dataset_url="gs://tunix-data/ultrachat_tokenizado.parquet",
  learning_rate=2e-5,
  lr_schedule="cosine_decay",
  batch_size_per_device=4,
  max_seq_length=4096,
  checkpoint_interval_steps=500
)`,
  },
  {
    id: 'sft-dataset',
    name: 'Iterator de Dataset (Dataset Iterator)',
    role: 'Pipeline de Dados em Streaming',
    category: 'data',
    description:
      'Gerencia o fluxo de dados do Conjunto de Treinamento externo, garantindo que o modelo receba lotes pré-processados durante o treinamento. O Tunix suporta fontes como TFDS e Parquet, permitindo também a integração de datasets personalizados.',
    inputs: ['Conjunto de Treinamento Externo (TFDS / Parquet / HuggingFace)'],
    outputs: ['Lote de tokens particionado (input_ids, attention_mask, rótulos)'],
    codeSnippet: `class DatasetIterator:
  def __iter__(self):
    for batch in tfds_stream.prefetch(4):
      yield jax.device_put(batch, sharding.NamedSharding(mesh, P('data', 'model')))`,
  },
  {
    id: 'sft-model',
    name: 'Modelo (nnx.Graph)',
    role: 'Entidade Central de Rede Neural',
    category: 'model',
    description:
      'Gerencia os LLMs inicializados (ex.: nnx.Graph) carregados com pesos de parâmetros externos, servindo como a entidade principal sendo treinada. O Tunix suporta modelos predefinidos (ex.: Gemma, Llama, Qwen) e permite novos modelos personalizados.',
    inputs: ['Parâmetros Externos do Modelo (Checkpoints GCS / SafeTensors)', 'Lote de Tokens'],
    outputs: ['Tensor de Logits [batch_size, seq_len, vocab_size]'],
    codeSnippet: `model = gemma.GemmaForCausalLM(
  config=model_config,
  rngs=nnx.Rngs(0)
)
# Particiona o grafo do modelo na malha 2D de TPUs
nnx.sharded_init(model, mesh=mesh, partition_spec=P('fsdp', 'tp'))`,
  },
  {
    id: 'sft-trainer',
    name: 'Treinador (Trainer)',
    role: 'Orquestrador de Passos',
    category: 'compute',
    description:
      'Orquestra os passos de treinamento coordenando as interações entre o modelo, dados e otimizador. Calcula a passada para frente (forward pass), perda (loss), gradientes da passada para trás e atualiza os estados.',
    inputs: ['Instância do Modelo', 'Lote de Dados', 'Estado do Otimizador'],
    outputs: ['Pesos do modelo atualizados', 'Escalar de perda (loss)', 'Métricas do passo'],
    codeSnippet: `@jax.jit
def train_step(model, opt_state, batch):
  def loss_fn(model):
    logits = model(batch['input_ids'], mask=batch['mask'])
    return optax.softmax_cross_entropy_with_integer_labels(logits, batch['labels']).mean()
  
  loss, grads = nnx.value_and_grad(loss_fn)(model)
  updates, new_opt_state = optimizer.update(grads, opt_state, model.params)
  model.update(updates)
  return loss, new_opt_state`,
  },
  {
    id: 'sft-optimizer',
    name: 'Otimizador (Optimizer - Optax)',
    role: 'Processador de Gradientes',
    category: 'compute',
    description:
      'Aplica algoritmos de otimização (ex.: AdamW) para atualizar os parâmetros do modelo com base na perda calculada, executando decaimento de peso (weight decay) e corte de gradiente (gradient clipping).',
    inputs: ['Gradientes da Perda (dLoss/dParams)'],
    outputs: ['Deltas de Parâmetros (Atualizações)'],
    codeSnippet: `optimizer = optax.chain(
  optax.clip_by_global_norm(1.0),
  optax.adamw(learning_rate=cosine_schedule, weight_decay=0.01)
)`,
  },
  {
    id: 'sft-checkpoint',
    name: 'Gerenciador de Checkpoints (Orbax)',
    role: 'Mecanismo de Persistência',
    category: 'storage',
    description:
      'Gerencia o salvamento periódico dos estados do modelo em armazenamento externo para recuperação do treino ou implantação. O Tunix aproveita a biblioteca Orbax para gerenciamento robusto e eficiente de checkpoints.',
    inputs: ['Pesos do Modelo (nnx.State)', 'Estado do Otimizador'],
    outputs: ['Artefatos de Checkpoint no GCS'],
    codeSnippet: `checkpointer = orbax.checkpoint.AsyncCheckpointer(
  orbax.checkpoint.PyTreeCheckpointHandler()
)
checkpointer.save(step_dir, args=orbax.checkpoint.args.PyTreeSave(model.state))`,
  },
  {
    id: 'sft-metrics',
    name: 'Registrador de Métricas (Metrics Logger)',
    role: 'Telemetria & Observabilidade',
    category: 'eval',
    description:
      'Captura dados de desempenho durante o treinamento (perda, taxa de aprendizado, norma do gradiente, tokens/s) e os exporta para bancos de dados externos para monitoramento e análise.',
    inputs: ['Perda do Passo (Loss)', 'Norma do Gradiente (GNorm)', 'Throughput de Tokens'],
    outputs: ['Métricas para TensorBoard / WandB / BigQuery'],
    codeSnippet: `metrics_logger.log_step(
  step=step_idx,
  loss=float(loss),
  grad_norm=float(gnorm),
  tokens_per_second=tokens_processed / step_time
)`,
  },
];

export const RL_COMPONENTS: PipelineComponent[] = [
  {
    id: 'rl-config',
    name: 'Configuração de RL (RL Config)',
    role: 'Hiperparâmetros Centrais',
    category: 'compute',
    description:
      'Fornece os hiperparâmetros centrais e as definições algorítmicas que inicializam todo o pipeline e determinam os objetivos de treinamento, como taxa de clip do PPO, coeficiente de penalidade KL e concorrência de rollout.',
    keyParams: [
      { name: 'algorithm', type: 'str', desc: 'PPO, GRPO ou DPO' },
      { name: 'kl_coeff', type: 'float', desc: 'Coeficiente de divergência KL (ex.: 0.05)' },
      { name: 'rollout_batch_size', type: 'int', desc: 'Total de trajetórias amostradas por iteração' },
      { name: 'sync_mode', type: 'enum', desc: 'SYNCHRONOUS ou ASYNCHRONOUS' },
    ],
    codeSnippet: `rl_config = RlConfig(
  algorithm="GRPO",
  actor_model="google/gemma-2-9b-it",
  reward_model="google/gemma-2-27b-reward",
  num_generations_per_prompt=8,
  clip_ratio=0.2,
  kl_coeff=0.04,
  sync_mode=SyncMode.ASYNC_ROLLOUT
)`,
  },
  {
    id: 'rl-orchestrator',
    name: 'Orquestrador Global (Orchestrator)',
    role: 'Gerenciador Global do Fluxo',
    category: 'compute',
    description:
      'Gerencia o fluxo de trabalho global, coordenando o Controle de Recursos, monitorando o progresso via Registrador de Métricas e direcionando a execução do algoritmo de RL escolhido (como PPO ou GRPO). Conduz transferências síncronas e assíncronas no pipeline.',
    codeSnippet: `class RlOrchestrator:
  def run_loop(self):
    while not self.converged():
      prompts = self.dataset.get_prompts()
      trajectories = self.rollout_workers.generate(prompts)
      evaluated = self.inference_workers.evaluate(trajectories)
      self.train_queue.put(evaluated)
      self.trainers.step()
      self.weight_sync.broadcast(self.trainers.actor_weights)`,
  },
  {
    id: 'rl-rollout',
    name: 'Workers de Rollout (vLLM / SGLang)',
    role: 'Amostradores de Trajetórias de Alta Vazão',
    category: 'compute',
    description:
      'Esses workers geram trajetórias de amostra a partir do modelo atual utilizando runtimes otimizados em C++ como vLLM ou SGLang. Isso assegura coleta de dados em altíssima velocidade, vital para um treinamento de RL eficiente.',
    inputs: ['Lotes de Prompts', 'Últimos Pesos do Ator (sincronizados dos Treinadores)'],
    outputs: ['Tokens de resposta gerados, log-probabilidades de amostragem'],
    codeSnippet: `class VLLMRolloutWorker:
  def sample(self, prompts, n_samples=8):
    sampling_params = SamplingParams(n=n_samples, temperature=0.7, top_p=0.95)
    return self.engine.generate(prompts, sampling_params)`,
  },
  {
    id: 'rl-inference',
    name: 'Workers de Inferência (Crítico / Ref / Recompensa)',
    role: 'Avaliadores de Trajetórias',
    category: 'eval',
    description:
      'Esses workers hospedam modelos de avaliação (ex.: modelos de crítico, referência e recompensa no PPO) para analisar as amostras coletadas. Eles calculam recompensas escalares, log-probabilidades de referência e estimativas de valor V(s).',
    inputs: ['Trajetórias (Prompt + Resposta Gerada)'],
    outputs: ['Recompensas Escalares, Log-probs de Referência, Estimativas de Valor V(s)'],
    codeSnippet: `# Avalia trajetórias amostradas
reward = reward_model(prompt, response)
ref_logprobs = reference_model.compute_logprobs(prompt, response)
values = critic_model.estimate_values(prompt, response)`,
  },
  {
    id: 'rl-queue',
    name: 'Fila de Dados de Treino (Train Data Queue)',
    role: 'Buffer em Memória com Streaming',
    category: 'data',
    description:
      'Este buffer em memória coleta amostras avaliadas das etapas de inferência e rollout e as envia em streaming para os treinadores, desacoplando a vazão de inferência da vazão de treinamento nas TPUs.',
    inputs: ['Lotes de Trajetórias Avaliadas'],
    outputs: ['Mini-lotes particionados para os dispositivos TPU do Treinador'],
    codeSnippet: `train_queue = AsyncShardedQueue(
  capacity=1024,
  prefetch_factor=2,
  sharding=device_mesh['data']
)`,
  },
  {
    id: 'rl-trainers',
    name: 'Treinadores (Ator & Crítico)',
    role: 'Atualizadores de Política e Valor',
    category: 'compute',
    description:
      'Executam atualizações de pesos para os modelos Ator (Actor) e Crítico (Critic) usando a diferenciação automática do JAX, corte de gradiente de política e GAE ou normalização em grupo no GRPO.',
    inputs: ['Mini-lotes da Fila de Dados de Treino'],
    outputs: ['Parâmetros Atualizados dos Modelos Ator e Crítico'],
    codeSnippet: `@jax.jit
def ppo_actor_step(actor_model, batch, advantages):
  def ppo_loss(actor):
    new_logprobs = actor.logprobs(batch.tokens)
    ratio = jnp.exp(new_logprobs - batch.old_logprobs)
    clipped_ratio = jnp.clip(ratio, 1 - 0.2, 1 + 0.2)
    surrogate = jnp.minimum(ratio * advantages, clipped_ratio * advantages)
    return -surrogate.mean()
  return nnx.value_and_grad(ppo_loss)(actor_model)`,
  },
  {
    id: 'rl-weightsync',
    name: 'Sincronização de Pesos (Weight Sync)',
    role: 'Ponte de Transmissão de Parâmetros',
    category: 'storage',
    description:
      'Uma Sincronização de Pesos subsequente propaga esses parâmetros atualizados de volta aos Workers de Rollout, garantindo que usem o modelo mais recente na próxima iteração.',
    inputs: ['Pesos Atualizados do Ator vindos dos Treinadores'],
    outputs: ['Pesos em memória atualizados nos workers vLLM/SGLang'],
    codeSnippet: `# Broadcast rápido de parâmetros dentro do cluster
def sync_weights_to_rollout(actor_model, rollout_workers):
  weights_dict = actor_model.export_weights()
  for worker in rollout_workers:
    worker.update_weights_async(weights_dict)`,
  },
];

export const AGENTIC_COMPONENTS: PipelineComponent[] = [
  {
    id: 'agent-core',
    name: 'Agente (LLM Multi-Turno)',
    role: 'Planejador de Raciocínio & Ação',
    category: 'model',
    description:
      'Envolve-se em conversas de múltiplos turnos, decompondo problemas complexos em etapas sequenciais de raciocínio (cadeia de pensamento), invocação de ferramentas externas e geração da resposta final.',
    keyParams: [
      { name: 'max_turns', type: 'int', desc: 'Máximo de turnos de deliberação por tarefa' },
      { name: 'allowed_tools', type: 'list[str]', desc: 'Ações de ambiente permitidas' },
    ],
    codeSnippet: `# Passo do Agente no Tunix
thought, action = agent.generate_thought_and_action(
  conversation_history,
  tools_available=[python_interpreter, web_search]
)`,
  },
  {
    id: 'agent-env',
    name: 'Ambiente & Executor de Ferramentas',
    role: 'Simulador do Mundo & Host de APIs',
    category: 'compute',
    description:
      'Gerencia a execução de ferramentas (ex.: busca na web, execução de código Python, APIs) para coletar dados ou executar ações; o ambiente controla a execução segura e fornece observações de volta ao agente para os passos seguintes.',
    inputs: ['Payload da Chamada de Ferramenta (nome da função, argumentos)'],
    outputs: ['Observação da Ferramenta (stdout, resposta JSON, código de saída)'],
    codeSnippet: `observation = environment.execute_tool(
  name=action.tool_name,
  args=action.tool_args,
  timeout_seconds=15
)`,
  },
  {
    id: 'agent-async-pipeline',
    name: 'Rollout & Treinamento Assíncronos',
    role: 'Pipeline de Sobreposição de Latência',
    category: 'compute',
    description:
      'Sobrepõe a latência de inferência do modelo, a execução de ferramentas limitada por E/S (I/O) e o cálculo de recompensas. Enquanto um worker executa chamadas de E/S em sandbox, os recursos de TPU processam outras trajetórias para maximizar a utilização do hardware.',
    codeSnippet: `# Rollout assíncrono em pipeline
async def async_agent_rollout(prompt):
  history = [prompt]
  while not finished:
    tpu_future = dispatch_inference(history)
    action = await tpu_future
    io_future = dispatch_tool_sandbox(action)
    observation = await io_future
    history.append(observation)`,
  },
  {
    id: 'agent-grouping',
    name: 'Loteamento & Agrupamento de Trajetórias (GRPO)',
    role: 'Otimizador de Política Eficiente em Amostras',
    category: 'compute',
    description:
      'Suporta nativamente o loteamento e agrupamento de trajetórias, tornando-se compatível com algoritmos como o GRPO, que exigem múltiplas amostras por prompt para aprendizado robusto sem a necessidade de um modelo de crítico separado.',
    codeSnippet: `# Normalização de Vantagem GRPO através de G trajetórias amostradas
def compute_grpo_advantages(rewards):
  # shape de rewards: [batch_size, G]
  mean_r = jnp.mean(rewards, axis=-1, keepdims=True)
  std_r = jnp.std(rewards, axis=-1, keepdims=True) + 1e-8
  return (rewards - mean_r) / std_r`,
  },
];
