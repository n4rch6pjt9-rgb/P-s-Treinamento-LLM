export type SectionId = 
  | 'overview' 
  | 'high-level-architecture' 
  | 'sft' 
  | 'rl' 
  | 'agentic-rl' 
  | 'interactive-simulator' 
  | 'config-explorer';

export interface TocItem {
  id: SectionId;
  title: string;
  badge?: string;
  subitems?: {
    id: string;
    title: string;
  }[];
}

export interface ArchitectureLayer {
  id: string;
  number: number;
  name: string;
  description: string;
  color: string;
  bgLight: string;
  borderColor: string;
  components: {
    id: string;
    name: string;
    tagline: string;
    details: string;
    tech?: string[];
    docsRef?: string;
  }[];
}

export interface PipelineComponent {
  id: string;
  name: string;
  role: string;
  category: 'data' | 'model' | 'compute' | 'storage' | 'eval';
  description: string;
  inputs?: string[];
  outputs?: string[];
  keyParams?: { name: string; type: string; desc: string }[];
  jaxPrimitive?: string;
  codeSnippet?: string;
}

export interface SimulationStep {
  id: string;
  title: string;
  description: string;
  activeComponentIds: string[];
  metrics?: Record<string, string | number>;
  logOutput?: string;
}
