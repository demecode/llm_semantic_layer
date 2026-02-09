export type TimeseriesPoint = { period: string; value: number };

export type ChatResponse = {
  answer: string;
  kpis?: Record<string, any> | null;
  series?: { name: string; data: TimeseriesPoint[] }[] | null;
  chart?: { type: string; x: string; y: string; unit?: string } | null;
    // ranking packs (Top-N)
  ranking?: {
    label: string;
    value: number;
  }[];
  meta?: any;
  data?: any;
};

export type MetricsResponse = {
  metrics: {
    name: string;
    label?: string;
    description?: string;
    type?: string;
    time_grains?: string[];
    filter?: any;
  }[];
};

export type SemanticModelsResponse = {
  semantic_models: Array<{
    name: string;
    description?: string;
    measures: string[];
    dimensions: string[];
    relation?: string | null;
  }>;
};