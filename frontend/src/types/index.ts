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
