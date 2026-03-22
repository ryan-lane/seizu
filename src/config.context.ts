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
  graph_settings?: GraphSettings;
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

export interface GraphSettings {
  node_label?: string;
  node_color_by?: string;
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
  schema_version?: number;
  name?: string;
  queries?: Record<string, string>;
  rows: Row[];
  inputs?: ReportInput[];
}

export interface AppConfig {
  [key: string]: unknown;
}

export interface ActionConfigFieldDef {
  name: string;
  label: string;
  type: 'string' | 'text' | 'number' | 'boolean' | 'string_list' | 'select';
  required?: boolean;
  description?: string;
  default?: unknown;
  options?: string[];
}

export interface SeizuConfig {
  config: AppConfig;
  stats: StatsConfig;
  scheduled_query_action_types: string[];
  scheduled_query_action_schemas: Record<string, ActionConfigFieldDef[]>;
}

export interface ConfigContextValue {
  config?: SeizuConfig;
}

// eslint-disable-next-line import/prefer-default-export
export const ConfigContext = createContext<ConfigContextValue>({});
