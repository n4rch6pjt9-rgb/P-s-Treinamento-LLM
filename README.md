# Pós-Treinamento LLM

Este repositório tem duas partes:

| Pasta | O que é |
|---|---|
| [`training/`](training/README.md) | Pipeline real de SFT (Tunix + LoRA, Gemma 3 1B-it) do classificador de escopo do LicitaGym. |
| raiz (`src/`) | **Explorador da Arquitetura Tunix**: app educativo e estático sobre SFT, RL e RL Agêntico. |

## Pipeline de SFT (`training/`)

Fine-tuning do Gemma 3 1B-it com LoRA para classificar itens de licitação. O modelo lê o item (mais o objeto da licitação) e responde `{"categoria": ...}`, com um destes rótulos: `forte`, `fraco`, `piso`, `borracha`, `obra_piso`, `manutencao` ou `fora`.

1. **Coletar:** `python export_dataset.py coletar`
2. **Pré-rotular:** `python rotular_gemini.py`
3. **Revisar:** uma pessoa confere `rotulos_sugeridos.csv` e gera `rotulos.csv`.
4. **Montar:** `python export_dataset.py montar` (divisão 70/15/15 por licitação)
5. **Treinar:** `sft_tunix.ipynb` no Colab (TPU v5e-1 ou T4), com a configuração em `config/sft_classificador.yaml`.
6. **Avaliar:** `python avaliar.py --baseline-regras <coletor>`

**Critério de aceite:** o macro-F1 no teste precisa superar o das regras atuais do coletor. Os dados (`training/data/`) ficam fora do git. Detalhes em [training/README.md](training/README.md).

---

# Explorador da Arquitetura Tunix

Aplicação web interativa (em português) que apresenta o design de sistema do **Tunix (Tune-in-JAX)**, framework nativo em JAX para pós-treinamento de LLMs. O app cobre três fluxos: **Supervised Fine-Tuning (SFT)**, **Reinforcement Learning (RL)** e **RL Agêntico**.

O projeto foi gerado a partir de um template do Google AI Studio e roda como uma SPA em React + Vite.

## Funcionalidades

- **Visão geral da arquitetura em camadas:** diagrama com 5 camadas (Interface & Aplicação, Algoritmos & Fluxos, Componentes Principais, Frameworks Fundamentais e Hardware). Clique em um componente para abrir um modal com detalhes, tecnologias e parâmetros.
- **Diagramas de pipeline:**
  - **SFT:** Config → Dataset Iterator → Modelo (`nnx.Graph`) → Trainer → Optimizer (Optax) → Checkpoint (Orbax) → Metrics Logger.
  - **RL:** Orquestrador, workers de rollout (vLLM / SGLang), workers de inferência (crítico/referência/recompensa), fila de dados, treinadores ator/crítico e sincronização de pesos (PPO, GRPO, DPO).
  - **RL Agêntico:** agente LLM multi-turno, ambiente e executor de ferramentas, rollout/treino assíncronos e agrupamento de trajetórias (GRPO).
- **Simulador de pipeline:** executa passo a passo uma iteração simulada de SFT, RL ou RL Agêntico, com logs e métricas fictícias (perda, norma do gradiente, LR, tokens/s).
- **Playground de configuração:** gera um YAML de job (SFT, RL/GRPO ou Agêntico) a partir de parâmetros ajustáveis (learning rate, tamanho de sequência, batch size, topologia TPU, engine de rollout), com botão de copiar.
- **Navegação:** sumário lateral com *scroll spy* e busca global (`Ctrl/⌘ + K`).

> Todo o conteúdo é estático e fica em `src/data/tunixData.ts` e nos próprios componentes. O simulador não executa treinamento real.
>
> Os YAML do Playground usam `gemma-2-9b` como exemplo (UltraChat, GRPO de matemática). A configuração usada de fato no treino do LicitaGym é [`training/config/sft_classificador.yaml`](training/config/sft_classificador.yaml).

## Stack

| Área | Tecnologia |
|---|---|
| UI | React 19, TypeScript |
| Build/dev | Vite 8 |
| Estilo | Tailwind CSS 4 (`@tailwindcss/vite`) |
| Ícones / animação | `lucide-react`, `motion` |
| Fontes | Plus Jakarta Sans, JetBrains Mono (Google Fonts) |

## Estrutura

```
.
├── index.html                  # HTML base (pt-BR, metatags, fontes)
├── metadata.json               # Metadados do app no AI Studio
├── vite.config.ts              # Vite + React + Tailwind, alias "@" (raiz do projeto)
├── .env.example                # Variáveis de ambiente (template AI Studio)
├── training/                   # Pipeline de SFT do classificador (ver acima)
└── src/
    ├── main.tsx                # Ponto de entrada
    ├── App.tsx                 # Layout, navegação e modos de visualização
    ├── index.css               # Estilos globais / Tailwind
    ├── types.ts                # Tipos (SectionId, ArchitectureLayer, PipelineComponent…)
    ├── data/
    │   └── tunixData.ts        # Conteúdo: camadas e componentes SFT/RL/Agêntico
    └── components/
        ├── Navbar.tsx
        ├── TableOfContents.tsx
        ├── SearchModal.tsx
        ├── HighLevelArchitectureDiagram.tsx
        ├── SftPipelineDiagram.tsx
        ├── RlPipelineDiagram.tsx
        ├── AgenticRlDiagram.tsx
        ├── ComponentDetailModal.tsx
        ├── PipelineSimulator.tsx
        └── ConfigPlayground.tsx
```

## Como rodar

**Pré-requisito:** Node.js 20.19+ ou 22.12+ (exigência do Vite 8).

```bash
npm install
npm run dev        # http://localhost:3000
```

Outros scripts:

| Script | O que faz |
|---|---|
| `npm run build` | Gera o build de produção em `dist/` |
| `npm run preview` | Serve o build localmente |
| `npm run lint` | Checagem de tipos (`tsc --noEmit`) |
| `npm run clean` | Remove `dist/` (usa `rm -rf`: no Windows, rode no Git Bash ou WSL) |

### Variáveis de ambiente

O `.env.example` traz `GEMINI_API_KEY` e `APP_URL`, herdados do template do AI Studio. **Nenhuma delas é usada pelo código atual**, então o app roda sem configurar nada. Se for adicionar recursos com a API Gemini, copie para `.env.local` e preencha:

```bash
cp .env.example .env.local
```

## Editando o conteúdo

- Para alterar textos, componentes, parâmetros ou snippets de código dos diagramas, edite `src/data/tunixData.ts` (tipado por `src/types.ts`).
- Os passos do simulador ficam em `src/components/PipelineSimulator.tsx`.
- Os templates YAML ficam em `src/components/ConfigPlayground.tsx`.

## Observações

- As dependências `@google/genai`, `express` e `dotenv` vêm do template e não são usadas hoje; podem ser removidas se não houver planos de backend.
- O `metadata.json` declara `MAJOR_CAPABILITY_SERVER_SIDE_GEMINI_API`, também herdado do template. Só é relevante se o app for republicado no AI Studio.
- O `name` em `package.json` ainda é `react-example`; vale renomear (ex.: `tunix-architecture-explorer`).
- Números, caminhos `gs://` e métricas exibidos no explorador são ilustrativos.

## Licença

Os arquivos-fonte declaram `SPDX-License-Identifier: Apache-2.0`.
