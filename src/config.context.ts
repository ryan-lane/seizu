import { createContext } from 'react';

export interface StatsConfig {
  external_prefix: string;
  external_provider: string;
}

export interface PanelParam {
  name: string;
  value?: string;
  input_id?: string;
}

export interface Panel {
  type: string;
  cypher?: string;
  details_cypher?: string;
  metric?: string;
  caption?: string;
  size?: number;
  threshold?: number;
  params?: PanelParam[];
  pie_settings?: PieSettings;
  bar_settings?: BarSettings;
  table_id?: string;
  legend?: string;
  markdown?: string;
  columns?: ColumnDef[];
}

export interface PieSettings {
  legend?: string;
}

export interface BarSettings {
  legend?: string;
}

export interface ColumnDef {
  name: string;
  label: string;
}

export interface Row {
  name: string;
  panels: Panel[];
}

export interface ReportInput {
  input_id: string;
  type: string;
  cypher?: string;
  params?: Record<string, string>;
  label: string;
  default?: InputValue;
  size?: number;
}

export interface InputValue {
  label: string;
  value: string;
}

export interface Report {
  name: string;
  rows: Row[];
  inputs?: ReportInput[];
}

export interface AppConfig {
  queries: Record<string, string>;
}

export interface SeizuConfig {
  config: AppConfig;
  stats: StatsConfig;
}

export interface ConfigContextValue {
  config?: SeizuConfig;
}

// eslint-disable-next-line import/prefer-default-export
export const ConfigContext = createContext<ConfigContextValue>({});
