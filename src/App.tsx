/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { TableOfContents } from './components/TableOfContents';
import { HighLevelArchitectureDiagram } from './components/HighLevelArchitectureDiagram';
import { SftPipelineDiagram } from './components/SftPipelineDiagram';
import { RlPipelineDiagram } from './components/RlPipelineDiagram';
import { AgenticRlDiagram } from './components/AgenticRlDiagram';
import { ComponentDetailModal } from './components/ComponentDetailModal';
import { PipelineSimulator } from './components/PipelineSimulator';
import { ConfigPlayground } from './components/ConfigPlayground';
import { SearchModal } from './components/SearchModal';
import { SectionId } from './types';
import { 
  Layers, 
  Cpu, 
  Sparkles, 
  BookOpen, 
  ExternalLink, 
  FileText, 
  Play, 
  Settings, 
  Zap
} from 'lucide-react';

export default function App() {
  const [activeSection, setActiveSection] = useState<SectionId>('overview');
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'document' | 'simulator' | 'config'>('document');

  // Sincroniza a navegação entre as seções
  const scrollToSection = (sectionId: SectionId) => {
    setActiveSection(sectionId);
    if (sectionId === 'interactive-simulator') {
      setViewMode('simulator');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    if (sectionId === 'config-explorer') {
      setViewMode('config');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    setViewMode('document');
    const elem = document.getElementById(sectionId);
    if (elem) {
      elem.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // Observador de rolagem (Scroll spy)
  useEffect(() => {
    if (viewMode !== 'document') return;

    const sections = ['high-level-architecture', 'sft', 'rl', 'agentic-rl'];
    const handleScroll = () => {
      const scrollPos = window.scrollY + 160;
      for (const sec of sections) {
        const el = document.getElementById(sec);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollPos >= top && scrollPos < top + height) {
            setActiveSection(sec as SectionId);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [viewMode]);

  return (
    <div className="min-h-screen bg-[#fafbfc] text-slate-800 flex flex-col selection:bg-blue-100 selection:text-blue-900">
      {/* Cabeçalho de Navegação */}
      <Navbar
        activeSection={activeSection}
        onSelectSection={scrollToSection}
        onOpenSearch={() => setIsSearchOpen(true)}
        onOpenComponentDetail={(id) => setSelectedComponentId(id)}
      />

      {/* Conteúdo Principal */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Seletor de Modo de Exibição */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8 pb-4 border-b border-slate-200">
          <div className="flex items-center gap-1.5 p-1 bg-slate-100/90 rounded-xl text-xs font-semibold text-slate-600">
            <button
              onClick={() => setViewMode('document')}
              className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                viewMode === 'document'
                  ? 'bg-white text-slate-900 shadow-2xs font-bold'
                  : 'hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-blue-600" />
              Visão Geral do Design
            </button>
            <button
              onClick={() => setViewMode('simulator')}
              className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                viewMode === 'simulator'
                  ? 'bg-white text-indigo-900 shadow-2xs font-bold'
                  : 'hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <Play className="w-3.5 h-3.5 text-indigo-600 fill-indigo-600" />
              Simulador Interativo
            </button>
            <button
              onClick={() => setViewMode('config')}
              className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                viewMode === 'config'
                  ? 'bg-white text-slate-900 shadow-2xs font-bold'
                  : 'hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <Settings className="w-3.5 h-3.5 text-slate-600" />
              Especificações & Gerador de Config
            </button>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
            <span className="hidden sm:inline">JAX 0.4.30+ • Flax NNX • TPU v5p</span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Pronto para Produção
            </span>
          </div>
        </div>

        {/* VISÃO 1: DOCUMENTAÇÃO COMPLETA */}
        {viewMode === 'document' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Coluna Esquerda: Artigo & Conteúdo */}
            <article className="lg:col-span-9 max-w-4xl space-y-12">
              {/* Cabeçalho do Documento & Introdução */}
              <section id="overview" className="space-y-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 px-2.5 py-0.5 rounded-md border border-blue-200">
                    Arquitetura de Sistema
                  </span>
                  <span className="text-xs text-slate-400 font-mono">• Tune-in-JAX</span>
                </div>

                <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                  Visão Geral do Design
                </h1>

                <p className="text-base sm:text-lg text-slate-600 leading-relaxed pt-1">
                  Este documento fornece uma visão geral do <strong>Tunix (Tune-in-JAX)</strong>, um framework nativo em JAX
                  para pós-treinamento de grandes modelos de linguagem (LLMs). Ele aborda a arquitetura geral em camadas
                  e as arquiteturas de loop de treinamento para <strong>Supervised Fine-Tuning (SFT)</strong>,{' '}
                  <strong>Reinforcement Learning (RL)</strong> e <strong>RL Agêntico</strong>. Compreender este design
                  ajudará você a utilizar e estender o Tunix com facilidade para o ajuste de modelos.
                </p>

                {/* SUMÁRIO INTERATIVO */}
                <div id="table-of-contents">
                  <TableOfContents
                    activeSection={activeSection}
                    onSelectSection={scrollToSection}
                    inline={true}
                  />
                </div>
              </section>

              {/* SEÇÃO 1: Arquitetura de Alto Nível */}
              <section id="high-level-architecture" className="space-y-5 pt-4 scroll-mt-24 border-t border-slate-200">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-700">
                    <Layers className="w-4 h-4" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
                    Arquitetura de Alto Nível
                  </h2>
                </div>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  O diagrama abaixo ilustra a arquitetura em camadas do Tunix:
                </p>

                <ul className="space-y-3 text-sm text-slate-700 list-disc pl-5 leading-relaxed">
                  <li>
                    <strong className="text-slate-900">Camada de Interface do Usuário & Aplicação:</strong> Esta camada superior fornece os principais pontos de acesso para usuários por meio de ferramentas CLI, notebooks interativos e arquivos de configuração para definir e gerenciar experimentos de ajuste. Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('cli-tools')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Iniciar Jobs (launching.md) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                  <li>
                    <strong className="text-slate-900">Camada de Algoritmos & Fluxos de Trabalho:</strong> Esta camada abriga os paradigmas centrais de treinamento, incluindo ajuste fino supervisionado (SFT), aprendizado por reforço (RL) e fluxos agênticos, suportando diversas estratégias de otimização de modelos. Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('sft-algo')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Algoritmos Suportados (algorithms.md) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                  <li>
                    <strong className="text-slate-900">Camada de Componentes Principais:</strong> Responsável pelo funcionamento interno do sistema, esta camada gerencia a orquestração do loop de treinamento, o rastreamento de métricas e o gerenciamento de estado distribuído complexo necessário para execuções em larga escala.
                  </li>
                  <li>
                    <strong className="text-slate-900">Camada de Frameworks Fundamentais & Integração:</strong> Esta camada integra bibliotecas subjacentes de alto desempenho como JAX, Flax e Optax para fornecer computação acelerada, primitivas de redes neurais e otimização eficiente de gradientes.
                  </li>
                  <li>
                    <strong className="text-slate-900">Camada de Hardware:</strong> A base da pilha gerencia os recursos de computação físicos ou virtuais, especificamente otimizados para Google Cloud TPUs, clusters multi-host de GPU e hosts de CPU.
                  </li>
                </ul>

                {/* DIAGRAMA 1: Arquitetura Tunix */}
                <HighLevelArchitectureDiagram
                  onSelectComponent={(compId) => setSelectedComponentId(compId)}
                />
              </section>

              {/* SEÇÃO 2: SFT */}
              <section id="sft" className="space-y-5 pt-4 scroll-mt-24 border-t border-slate-200">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-700">
                    <Cpu className="w-4 h-4" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
                    Supervised Fine-Tuning (SFT)
                  </h2>
                </div>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  O Ajuste Fino Supervisionado (Supervised Fine-Tuning - SFT) é uma técnica fundamental em machine learning
                  usada para adaptar modelos pré-treinados a tarefas específicas downstream por meio de treinamento em um conjunto
                  de dados rotulado. No Tunix, o pipeline de SFT foi projetado para ajustar de maneira altamente eficiente
                  grandes modelos de linguagem (LLMs) usando diversos datasets e estratégias de otimização, aproveitando o ecossistema JAX subjacente.
                </p>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  O diagrama a seguir ilustra o pipeline de Supervised Fine-Tuning (SFT) no Tunix, demonstrando o fluxo de dados e de controle.
                </p>

                {/* DIAGRAMA 2: Pipeline SFT */}
                <SftPipelineDiagram
                  onSelectComponent={(compId) => setSelectedComponentId(compId)}
                />

                {/* Lista Detalhada de Componentes */}
                <ul className="space-y-4 text-sm text-slate-700 list-disc pl-5 leading-relaxed">
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('sft-config')}
                    >
                      Configuração (Config):
                    </strong>{' '}
                    Gerencia as configurações de todos os componentes do pipeline, como detalhes do conjunto de dados (ex.: URL), especificações do modelo (ex.: URL, tokenizador), parâmetros do treinador (ex.: passos máximos, hiperparâmetros) e frequência de checkpoints (ex.: salvar a cada N passos). Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('sft-config')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Explicação de Config (launching.md#config-explanation) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('sft-dataset')}
                    >
                      Iterator de Dataset (Dataset Iterator):
                    </strong>{' '}
                    Gerencia o fluxo contínuo de dados do Conjunto de Treinamento externo, assegurando que o modelo receba lotes pré-processados durante o processo de treino. O Tunix oferece suporte nativo a várias fontes de dados como TFDS e Parquet, permitindo também a integração de datasets customizados.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('sft-model')}
                    >
                      Modelo (Model):
                    </strong>{' '}
                    Gerencia os LLMs inicializados (ex.: nnx.Graph) carregados com pesos de parâmetros externos (Model Params), funcionando como a entidade central sendo treinada. O Tunix oferece suporte a um conjunto de modelos predefinidos (ex.: Gemma, Llama, Qwen) e possibilita a integração de novos modelos customizados. Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('sft-model')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Modelos (models.md) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('sft-trainer')}
                    >
                      Treinador (Trainer):
                    </strong>{' '}
                    Orquestra os passos de treinamento coordenando as interações entre o modelo, os dados e o otimizador.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('sft-optimizer')}
                    >
                      Otimizador (Optimizer):
                    </strong>{' '}
                    Aplica algoritmos de otimização (ex.: AdamW) para atualizar os parâmetros do modelo com base na perda calculada.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('sft-checkpoint')}
                    >
                      Gerenciador de Checkpoints (Checkpoint Manager):
                    </strong>{' '}
                    Gerencia o salvamento periódico dos estados do modelo em armazenamento externo para recuperação do treinamento ou implantação do modelo em produção. O Tunix utiliza a biblioteca Orbax para um salvamento de checkpoints robusto, distribuído e não bloqueante.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('sft-metrics')}
                    >
                      Registrador de Métricas (Metrics Logger):
                    </strong>{' '}
                    Captura dados de desempenho durante o treinamento e os exporta para bancos de dados externos e painéis de observabilidade para monitoramento contínuo. Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('sft-metrics')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Métricas (metrics.md) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                </ul>
              </section>

              {/* SEÇÃO 3: RL */}
              <section id="rl" className="space-y-5 pt-4 scroll-mt-24 border-t border-slate-200">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center text-purple-700">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
                    Reinforcement Learning (RL)
                  </h2>
                </div>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  O Aprendizado por Reforço (Reinforcement Learning - RL) é um paradigma onde um agente aprende a tomar decisões
                  interagindo com um ambiente para maximizar uma recompensa acumulada. O Tunix fornece uma estrutura abrangente
                  para RL, projetada para suportar vários algoritmos (PPO, GRPO, DPO) e estratégias de otimização, aproveitando
                  o ecossistema JAX de alta performance.
                </p>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  O diagrama a seguir ilustra um pipeline típico de Reinforcement Learning (RL) no Tunix. Os detalhes exatos do pipeline
                  podem variar com base no algoritmo de RL específico em uso.
                </p>

                {/* DIAGRAMA 3: Pipeline RL */}
                <RlPipelineDiagram
                  onSelectComponent={(compId) => setSelectedComponentId(compId)}
                />

                {/* Lista Detalhada de Componentes */}
                <ul className="space-y-4 text-sm text-slate-700 list-disc pl-5 leading-relaxed">
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('rl-config')}
                    >
                      Configuração de RL (RL Config):
                    </strong>{' '}
                    Fornece os hiperparâmetros centrais e as definições algorítmicas que inicializam todo o pipeline e definem os objetivos do treinamento. Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('rl-config')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Explicação de Config (launching.md#config-explanation) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('rl-orchestrator')}
                    >
                      Orquestrador (Orchestrator):
                    </strong>{' '}
                    Gerencia o fluxo de trabalho global, coordenando o <strong className="text-slate-900">Controle de Recursos</strong>, monitorando o progresso através do <strong className="text-slate-900">Registrador de Métricas</strong> e dirigindo a execução do algoritmo de RL escolhido (como PPO ou GRPO). Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('rl-orchestrator')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Algoritmos Suportados (algorithms.md) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('rl-rollout')}
                    >
                      Workers de Rollout (Rollout Workers):
                    </strong>{' '}
                    Esses workers geram trajetórias de amostra a partir do modelo atual utilizando runtimes de inferência otimizados como o <strong className="text-slate-900 font-mono">vLLM</strong> ou <strong className="text-slate-900 font-mono">SGLang</strong>. Isso garante coleta de dados com altíssima taxa de transferência, essencial para um treino de RL eficiente. Consulte{' '}
                    <button
                      onClick={() => setSelectedComponentId('rl-rollout')}
                      className="text-blue-600 hover:underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Rollout (rollout.md) <ExternalLink className="w-3 h-3" />
                    </button>{' '}
                    para mais detalhes.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('rl-inference')}
                    >
                      Workers de Inferência (Inference Workers):
                    </strong>{' '}
                    Esses workers hospedam modelos de avaliação (ex.: modelo de crítico, referência e modelos de recompensa no PPO) para avaliar as amostras coletadas. Eles calculam recompensas, log-probabilidades de referência e estimativas de valor.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('rl-queue')}
                    >
                      Fila de Dados de Treino (Train Data Queue):
                    </strong>{' '}
                    Este buffer em memória reúne amostras avaliadas das etapas de inferência e rollout e as transmite em fluxo diretamente para os treinadores.
                  </li>
                  <li>
                    <strong
                      className="text-slate-900 cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={() => setSelectedComponentId('rl-trainers')}
                    >
                      Treinadores (Trainers):
                    </strong>{' '}
                    Executam atualizações de parâmetros nos modelos <strong className="text-slate-900">Ator (Actor)</strong> e <strong className="text-slate-900">Crítico (Critic)</strong>. Uma etapa subsequente de <strong className="text-slate-900">Sincronização de Pesos (Weight Sync)</strong> propaga esses pesos atualizados de volta aos Workers de Rollout, garantindo que usem o modelo mais recente na iteração seguinte.
                  </li>
                </ul>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed pt-2">
                  O <strong className="text-slate-900">Orquestrador</strong> comanda o loop geral de treinamento por RL. Em cada iteração, os <strong className="text-slate-900">Workers de Rollout</strong> geram trajetórias de amostra interagindo com o ambiente. Essas trajetórias são passadas para os <strong className="text-slate-900">Workers de Inferência</strong> para avaliação, computando valores fundamentais como recompensas escalares e log-probabilidades. As amostras avaliadas são reunidas e consumidas pelos <strong className="text-slate-900">Treinadores</strong> para atualizar os modelos Ator e Crítico. Por fim, a <strong className="text-slate-900">Sincronização de Pesos</strong> transmite os novos parâmetros de volta aos Workers de Rollout, preparando o sistema para a próxima iteração. Todo esse processo pode ser orquestrado de maneira síncrona ou assíncrona (ex.: carregamento assíncrono de dados, rollout assíncrono sobreposto à computação em TPU).
                </p>
              </section>

              {/* SEÇÃO 4: RL Agêntico */}
              <section id="agentic-rl" className="space-y-5 pt-4 scroll-mt-24 border-t border-slate-200">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center text-amber-700">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
                    Reinforcement Learning Agêntico (Agentic RL)
                  </h2>
                </div>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  O Aprendizado por Reforço Agêntico no Tunix fornece uma arquitetura moderna para treinar
                  agentes capazes de realizar raciocínio em múltiplos turnos e interagir dinamicamente com ferramentas externas.
                  O design segue o paradigma padrão de RL onde um <strong className="text-slate-900">Agente</strong> interage com um{' '}
                  <strong className="text-slate-900">Ambiente</strong> ao longo de múltiplos passos para concluir uma tarefa com sucesso.
                </p>

                {/* DIAGRAMA 4: Fluxo de RL Agêntico */}
                <AgenticRlDiagram
                  onSelectComponent={(compId) => setSelectedComponentId(compId)}
                />

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  A estrutura central oferece suporte a agentes que participam de <strong className="text-slate-900">conversas multi-turno</strong>,
                  decompondo problemas intrincados em etapas sequenciais de raciocínio lógico (cadeia de pensamento),
                  invocação de ferramentas e geração de resposta final. Os agentes podem utilizar <strong className="text-slate-900">ferramentas externas</strong> (ex.:
                  pesquisa web, interpretador de código Python, APIs REST) para coletar informações ou executar ações; o ambiente
                  gerencia a execução segura e fornece observações de volta ao agente para os passos subsequentes.
                </p>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  Um dos principais focos do design é o desempenho e a escalabilidade, alcançados através de uma{' '}
                  <strong className="text-slate-900">arquitetura altamente assíncrona tanto para rollout quanto para treino</strong>. O pipeline de
                  coleta de trajetórias é desenvolvido para alta vazão, permitindo que muitas interações agente-ambiente sejam executadas concorrentemente.
                  Esse design sobrepõe com eficiência a latência de inferência do modelo, a execução de ferramentas em E/S e os cálculos de recompensa,
                  maximizando o aproveitamento de hardware (TPUs) e possibilitando um treinamento online ágil e sustentável.
                </p>

                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  O framework oferece suporte nativo a <strong className="text-slate-900">loteamento e agrupamento de trajetórias</strong>,
                  sendo totalmente compatível com algoritmos de ponta como o GRPO (Group Relative Policy Optimization), que exige
                  múltiplas trajetórias por prompt para aprendizado estável sem requerer uma rede de crítico separada.
                </p>
              </section>
            </article>

            {/* Coluna Direita: Sumário Fixo & Resumo Técnico */}
            <aside className="hidden lg:block lg:col-span-3 space-y-4 sticky top-24">
              <TableOfContents
                activeSection={activeSection}
                onSelectSection={scrollToSection}
                inline={false}
              />

              {/* Caixa de Especificações Principais */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs space-y-3">
                <div className="font-bold text-slate-900 flex items-center gap-1.5 pb-2 border-b border-slate-200">
                  <Zap className="w-3.5 h-3.5 text-blue-600" />
                  Especificações Principais
                </div>
                <div className="space-y-1.5 text-[11px] text-slate-600">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Backend:</span>
                    <span className="font-mono font-semibold text-slate-800">JAX (OpenXLA)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Módulos NN:</span>
                    <span className="font-mono font-semibold text-slate-800">Flax NNX Graph</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Checkpoints:</span>
                    <span className="font-mono font-semibold text-slate-800">Orbax Async</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Motores Rollout:</span>
                    <span className="font-mono font-semibold text-slate-800">vLLM & SGLang</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Clusters Alvo:</span>
                    <span className="font-mono font-semibold text-slate-800">Google Cloud TPUs</span>
                  </div>
                </div>
              </div>
            </aside>
          </div>
        )}

        {/* VISÃO 2: SIMULADOR INTERATIVO */}
        {viewMode === 'simulator' && (
          <div className="space-y-6">
            <PipelineSimulator />
          </div>
        )}

        {/* VISÃO 3: ESPECIFICAÇÕES DE CONFIG */}
        {viewMode === 'config' && (
          <div className="space-y-6">
            <ConfigPlayground />
          </div>
        )}
      </main>

      {/* Rodapé */}
      <footer className="mt-16 border-t border-slate-200 bg-white py-8 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-800">Tunix (Tune-in-JAX)</span>
            <span>—</span>
            <span>Framework nativo em JAX para pós-treinamento de LLMs</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>SFT</span>
            <span>•</span>
            <span>RL (PPO/GRPO)</span>
            <span>•</span>
            <span>RL Agêntico</span>
            <span>•</span>
            <span>Escalabilidade em Pods de TPU</span>
          </div>
        </div>
      </footer>

      {/* Modal de Detalhes do Componente */}
      <ComponentDetailModal
        componentId={selectedComponentId}
        onClose={() => setSelectedComponentId(null)}
      />

      {/* Modal de Busca Rápida (Cmd+K / Ctrl+K) */}
      <SearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onSelectComponent={(id) => setSelectedComponentId(id)}
        onSelectSection={(sec) => scrollToSection(sec)}
      />
    </div>
  );
}
