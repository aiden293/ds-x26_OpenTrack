"use client";
import { useEffect, useId, useState, type ReactNode } from "react";
import { EstimateNotes } from "@/components/estimate-notes";
import { WEEKDAYS, count, days, pct, useCountUp, weekdayOf } from "@/lib/format";
import type { EstimateRequest, Insights, Prediction } from "@/types";

/** (i) toggle: `button` goes next to a heading, `text` renders the explanation wherever the caller puts it. */
export function useInfo(label: string, content: ReactNode) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return {
    button: <button type="button" className="ib" aria-expanded={open} aria-controls={id} aria-label={label} onClick={() => setOpen(!open)}>i</button>,
    text: open ? <p className="note ibx" id={id}>{content}</p> : null,
  };
}

function modelStatus(result: Prediction) {
  const src = (used: string) => used === "ml" ? "prediction model" : "historical baseline";
  if (result.used_model === "ml" && result.p80_used_model === "ml") return <><b>Model estimate.</b> Both numbers come from the trained prediction model, using queue conditions as of {result.state_time.slice(0, 10)}.</>;
  if (result.used_model !== "ml" && result.p80_used_model !== "ml") return <><b>Historical estimate.</b> Based on the per-type median and 80th percentile of past closed requests.</>;
  return <><b>Mixed estimate.</b> Typical wait: {src(result.used_model)}. Longer estimate: {src(result.p80_used_model)}.</>;
}

const UPPER = [1, 2, 4, 7, 14, 30, Infinity];

function Distribution({ insights, p50, type }: { insights: Insights; p50: number; type: string }) {
  const { shares, labels } = insights.distribution;
  const [grown, setGrown] = useState(false);
  useEffect(() => { const f = requestAnimationFrame(() => setGrown(true)); return () => cancelAnimationFrame(f); }, []);
  if (!shares.length) return <p className="note">Too few past requests of this type to show.</p>;
  const max = Math.max(...shares);
  const mine = UPPER.findIndex(u => p50 < u);
  return <>
    <h3>How long requests like this took</h3>
    <p className="note" style={{ margin: 0 }}>Share of closed {type.toLowerCase()} requests by time to close. Highlighted: your typical wait.</p>
    <div className="hist">{shares.map((v, i) =>
      <div key={labels[i]} className={i === mine ? "hc me" : "hc"} style={{ ["--i" as string]: i }}>
        <span>{Math.round(v * 100)}%</span>
        <div className="hb" style={{ height: grown ? `${Math.max((v / max) * 88, 2).toFixed(1)}px` : 0 }} />
        <span>{labels[i]}</span>
      </div>)}
    </div>
  </>;
}

function Compare({ insights, request }: { insights: Insights; request: EstimateRequest }) {
  const [metric, setMetric] = useState<0 | 1>(0);
  const info = useInfo("About this comparison", "Model estimates for the same request type, date and time in each neighborhood, with October 2025 queue conditions. Small grey numbers are past requests of this type there (2022–2025); below about 50, treat differences as rough. Differences reflect past records, such as the mix of jobs, reporting habits and crew schedules; they are not a promise or a cause.");
  const value = (r: Insights["compare"][number]) => metric ? r.p80 : r.p50;
  const rows = [...insights.compare].sort((a, b) => value(a) - value(b));
  if (!rows.length) return <p className="note">Comparison is not available for this request.</p>;
  const max = Math.max(...rows.map(value));
  const k = rows.findIndex(r => r.neighborhood === request.neighborhood);
  const me = rows[k];
  const lo = rows[0], hi = rows[rows.length - 1];
  const label = metric ? "\"Allow longer\" time" : "typical wait";
  const wd = WEEKDAYS[weekdayOf(request.open_date)];
  const summary = me
    ? `Filed on a ${wd}, the ${label} in ${me.neighborhood} is ${days(value(me))}, ${k === 0 ? "the shortest" : k === rows.length - 1 ? "the longest" : `#${k + 1} shortest`} of ${rows.length} neighborhoods. Range: ${days(value(lo))} (${lo.neighborhood}) to ${days(value(hi))} (${hi.neighborhood}).`
    : `Filed on a ${wd}, the ${label} across ${rows.length} neighborhoods ranges from ${days(value(lo))} (${lo.neighborhood}) to ${days(value(hi))} (${hi.neighborhood}).`;
  return <>
    <h3>Same request, other neighborhoods{info.button}</h3>{info.text}
    <p className="note" style={{ margin: "6px 0" }}>{lo.neighborhood !== hi.neighborhood && value(lo) === value(hi)
      ? `The ${label} for this type comes from the citywide historical record, so it is the same in every neighborhood.`
      : summary}</p>
    <div className="flt">{(["Typical wait", "Allow longer"] as const).map((l, i) =>
      <button type="button" key={l} className={metric === i ? "on" : undefined} onClick={() => setMetric(i as 0 | 1)}>{l}</button>)}
    </div>
    <div className="cmp" role="list">{rows.map(r => {
      const cls = r.neighborhood === request.neighborhood ? "me" : "";
      return [
        <span key={`${r.neighborhood}-n`} className={cls} role="listitem" title={`${r.neighborhood} · ${r.n.toLocaleString()} past requests`}>{r.neighborhood} <small style={{ opacity: .7 }}>· {r.n.toLocaleString()}</small></span>,
        <span key={`${r.neighborhood}-b`} className={cls}><i style={{ width: `${max > 0 ? (value(r) / max) * 100 : 0}%` }} /></span>,
        <span key={`${r.neighborhood}-v`} className={cls}>{days(value(r))}</span>,
      ];
    })}</div>
  </>;
}

type Panel = "cmp" | "dist" | "det";
const PANELS: { key: Panel; label: string }[] = [
  { key: "cmp", label: "Other neighborhoods" }, { key: "dist", label: "How long it took" }, { key: "det", label: "Details" },
];

export function ResultCard({ request, result, insights, insightsError }: {
  request: EstimateRequest; result: Prediction; insights: Insights | null; insightsError: string;
}) {
  const [open, setOpen] = useState<Record<Panel, boolean>>({ cmp: false, dist: false, det: false });
  const [barGrown, setBarGrown] = useState(false);
  const c1 = useCountUp(result.p50, 1000, result);
  const c2 = useCountUp(result.p80, 1000, result);
  const c3 = useCountUp(result.n_support, 1000, result);
  useEffect(() => { const f = requestAnimationFrame(() => requestAnimationFrame(() => setBarGrown(true))); return () => cancelAnimationFrame(f); }, []);

  const hit = insights?.hit;
  const rate = hit?.rate ?? null;
  const hitText = !hit ? "Checking…" : rate !== null
    ? `In 2025, ${pct(rate)} of requests of this type closed within the "Allow longer" time this estimate would have given. Checked on ${hit.n.toLocaleString()} requests that were not used to build it.${hit.lower !== null && hit.unclosed_2025 !== null ? ` ${pct(hit.unclosed_2025)} of 2025 requests of this type never closed in the data and are not counted; if all of them counted as late, it would be ${pct(hit.lower)}.` : ""}`
    : `Too few 2025 requests of this type to check. Across all types, ${pct(hit.overall)} closed within "Allow longer".`;
  const hitInfo = useInfo("How this is checked", hitText);
  const panelBody = (key: Panel) => {
    if (insightsError && key !== "det") return <p className="note">{insightsError}</p>;
    if (!insights && key !== "det") return <p className="note">Loading…</p>;
    if (key === "cmp") return <Compare insights={insights!} request={request} />;
    if (key === "dist") return <Distribution insights={insights!} p50={result.p50} type={request.type} />;
    return <>
      <h3>Details</h3>
      <dl style={{ marginBottom: 12 }}>
        <div><dt>All days, this type</dt><dd>{days(result.baseline_p50)} typical</dd></div>
        <div><dt>In {request.neighborhood}, all days</dt><dd>{insights?.local.p50 != null ? `${days(insights.local.p50)} typical · ${insights.local.n.toLocaleString()} requests` : "Too few requests"}</dd></div>
        <div><dt>Requests behind this estimate</dt><dd>{count(c3)}</dd></div>
      </dl>
      <div className="status">{modelStatus(result)}</div>
    </>;
  };

  return <div className="card" aria-live="polite" id="rescard">
    <p className="note" style={{ margin: "0 0 10px" }}>{request.type} · {request.neighborhood} · filed on a {WEEKDAYS[weekdayOf(request.open_date)]}</p>
    <div className="tgl" role="group" aria-label="More about this estimate"><span>More:</span>
      {PANELS.map(p => <button type="button" key={p.key} aria-pressed={open[p.key]} onClick={() => setOpen(o => ({ ...o, [p.key]: !o[p.key] }))}>{p.label}</button>)}
    </div>
    <div className="mt"><div className="m main"><p>Typical wait</p><strong>{days(c1)}</strong><small>Median</small></div><div className="m"><p>Allow longer</p><strong>{days(c2)}</strong><small>8 in 10 done by then</small></div></div>
    <div className="conf">
      <div className="cf"><b>Chance it is done by &quot;Allow longer&quot;{hitInfo.button}</b><b className="hitv">{rate !== null ? pct(rate) : "–"}</b></div>
      <div className="bar"><i style={{ width: barGrown && rate !== null ? `${Math.round(rate * 100)}%` : 0 }} /></div>
      {hitInfo.text}
    </div>
    {(result.target_days !== null || result.p_ontime !== null) && <dl className="core">
      {result.target_days !== null && <div><dt>Estimated city target</dt><dd>{days(result.target_days)}</dd></div>}
      {result.p_ontime !== null && <div><dt>Chance of meeting city target</dt><dd>{pct(result.p_ontime)}</dd></div>}
    </dl>}
    <EstimateNotes notes={result.notes} />
    {PANELS.filter(p => open[p.key]).map(p => <div className="pnl" key={p.key}>{panelBody(p.key)}</div>)}
  </div>;
}
