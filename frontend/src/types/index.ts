export type Choices = { types: { type: string; n: number; demo: boolean }[]; neighborhoods: string[] };
export type EstimateRequest = { type: string; neighborhood: string; open_date: string };
export type Prediction = {
  p50: number; p80: number; baseline_p50: number; baseline_p80: number;
  target_days: number | null; p_ontime: number | null; n_support: number;
  used_model: string; p80_used_model: string; state_time: string;
  flags: string[]; pct_unclosed: number | null;
  notes?: { code: string; message: string }[];
};
export type SimilarCase = { case_enquiry_id: string; neighborhood: string; open_dt: string; closed_dt: string; resolution_days: number; closure_reason: string; match_level: string };
export type SimilarResult = { available: boolean; cases: SimilarCase[]; message?: string };

export type MetaType = { type: string; n: number; demo: boolean; group: number; hit: number | null; hit_n: number; pct_unclosed_2025: number | null };
export type Meta = {
  groups: string[]; types: MetaType[]; neighborhoods: string[]; hit_overall: number;
  stats: { cases: number | null; types: number; neighborhoods: number; years: string };
};
export type Insights = {
  hit: { rate: number | null; n: number; overall: number; unclosed_2025: number | null; lower: number | null };
  distribution: { labels: string[]; shares: number[]; n: number };
  local: { p50: number | null; n: number };
  compare: { neighborhood: string; p50: number; p80: number; n: number }[];
};
export type CaseSort = "rel" | "recent" | "old" | "short" | "long";
export type CaseScope = "nb" | "all";
export type CaseRow = {
  case_enquiry_id: string; neighborhood: string; open_dt: string; closed_dt: string; resolution_days: number;
  closure_reason: string | null; same_neighborhood: boolean; same_season: boolean; after_system_change: boolean; fastest: boolean;
};
export type CasesPage = { available: boolean; total: number; page: number; pages: number; cases: CaseRow[]; message?: string };
