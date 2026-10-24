"use client";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { EstimateNotes } from "@/components/estimate-notes";
import type { Choices, Prediction, SimilarResult, EstimateRequest } from "@/types";

function bostonNow() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date());
  const get = (key: string) => parts.find(p => p.type === key)?.value;
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}
const days = (n: number) => `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} days`;

export default function Home() {
  const [choices, setChoices] = useState<Choices | null>(null);
  const [type, setType] = useState("");
  const [neighborhood, setNeighborhood] = useState("");
  const [date, setDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [choiceError, setChoiceError] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<Prediction | null>(null);
  const [submitted, setSubmitted] = useState<EstimateRequest | null>(null);
  const [similar, setSimilar] = useState<SimilarResult | null>(null);
  const [similarError, setSimilarError] = useState("");
  async function loadChoices() {
    setChoiceError("");
    try {
      const data = await api<Choices>("choices"); setChoices(data);
      setType(data.types.find(t => t.type === "Request for Pothole Repair")?.type || data.types[0].type);
      setNeighborhood(data.neighborhoods.includes("Dorchester") ? "Dorchester" : data.neighborhoods[0]);
    } catch { setChoiceError("We couldn’t load request options. Check that the API is running, then retry."); }
  }
  useEffect(() => { setDate(bostonNow()); void loadChoices(); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(""); setResult(null); setSimilar(null); setSimilarError("");
    const request = { type, neighborhood, open_date: date };
    setSubmitted(request);
    await Promise.all([
      api<Prediction>("predict", request).then(setResult).catch(e => setError(e.message)),
      api<SimilarResult>("similar", request).then(setSimilar).catch(() => setSimilarError("Historical cases are temporarily unavailable.")),
    ]);
    setLoading(false);
  }
  return <>
    <header className="nav"><a className="brand" href="/" aria-label="Civic Pulse home"><span className="brand-icon">↗</span> civic<span>pulse</span></a><span className="nav-label">BOSTON, MA <span className="dot" /></span></header>
    <main>
      <section className="intro"><p className="eyebrow">A LITTLE MORE CLARITY FOR YOUR CITY</p><h1>Your request.<br />A clearer timeline.</h1><p className="lead">Get a sense of how long your Boston 311 request might take, informed by the city’s past service requests.</p><span className="tag">Boston 311 · Historical estimates</span></section>
      <div className="workspace">
        <section className="panel form-panel"><div className="section-heading"><span className="step">01</span><h2>Tell us about your request</h2></div><p className="muted">Start with a few details. No personal information needed.</p>
          {choiceError ? <div role="alert" className="error">{choiceError}<button className="text-button" onClick={loadChoices}>Retry loading options</button></div> : !choices ? <p role="status">Loading request options…</p> :
          <form onSubmit={submit}><fieldset disabled={loading}>
            <label htmlFor="type">Request type</label><select id="type" value={type} onChange={e => setType(e.target.value)} required><optgroup label="Featured requests">{choices.types.filter(t => t.demo).map(t => <option key={t.type}>{t.type}</option>)}</optgroup><optgroup label="All other requests">{choices.types.filter(t => !t.demo).map(t => <option key={t.type}>{t.type}</option>)}</optgroup></select>
            <label htmlFor="neighborhood">Neighborhood</label><select id="neighborhood" value={neighborhood} onChange={e => setNeighborhood(e.target.value)} required>{choices.neighborhoods.map(n => <option key={n}>{n}</option>)}</select>
            <label htmlFor="date">Request date & time</label><input id="date" type="datetime-local" value={date} onChange={e => setDate(e.target.value)} required /><p className="field-note">Boston local time (Eastern). Timing can affect your estimate.</p>
            <button className="primary" disabled={!date || loading} type="submit">{loading ? "Calculating your estimate…" : "Estimate resolution time"}<span aria-hidden="true">↗</span></button>
          </fieldset></form>}
          <p className="privacy">This tool estimates wait times. It does not submit a 311 request.</p>
        </section>
        <section className="panel results" aria-live="polite" aria-busy={loading}><div className="section-heading"><span className="step">02</span><h2>Your estimated timeline</h2></div>
          {error ? <div role="alert" className="error">{error}</div> : result ? <>
            <p className="result-context">{submitted?.type} · {submitted?.neighborhood}</p>
            <p className="field-note">Requested {submitted?.open_date.replace("T", " at ")} · Eastern time</p>
            <div className="metric-grid"><div className="metric main-metric"><p>Typical wait</p><strong>{days(result.p50)}</strong><small>Estimated median resolution time</small></div><div className="metric"><p>Allow a little longer</p><strong>{days(result.p80)}</strong><small>Estimated 80th percentile of resolution time</small></div></div>
            <dl className="details"><div><dt>Estimated city target</dt><dd>{result.target_days === null ? "Not available" : days(result.target_days)}</dd></div><div><dt>Chance of meeting that target</dt><dd>{result.p_ontime === null ? "Not available for this request" : `${Math.round(result.p_ontime * 100)}%`}</dd></div><div><dt>Historical typical wait</dt><dd>{days(result.baseline_p50)}</dd></div><div><dt>Historical cases for this type</dt><dd>{result.n_support.toLocaleString()}</dd></div></dl>
            <p className="field-note">Typical estimate: {result.used_model === "ml" ? "prediction model" : "historical baseline"}. Longer estimate: {result.p80_used_model === "ml" ? "prediction model" : "historical baseline"}.</p>
            <EstimateNotes notes={result.notes} />
          </> : <div className="empty"><div className="clock" aria-hidden="true">◷</div><h3>{loading ? "Finding your timeline" : "A better idea of what comes next"}</h3><p>{loading ? "Checking historical patterns for your request…" : "Choose your request details to see a typical wait, a longer timeframe, and historical context."}</p><div className="timeline" aria-hidden="true"><i /><span /><i /><span /><i /></div><div className="timeline-labels"><span>Request</span><span>Estimate</span><span>Resolution</span></div></div>}
        </section>
      </div>
      {result && <section className="panel history"><div className="section-heading"><span className="step">03</span><h2>Similar past requests</h2></div><p className="muted">Real closed cases, matched by request type, season, and neighborhood when possible.</p>
        {similarError ? <p role="status">{similarError}</p> : !similar ? <p>Loading historical cases…</p> : !similar.available ? <p className="notice">{similar.message} Your prediction is available independently.</p> : similar.cases.length === 0 ? <p>No matching closed cases were found before this request date.</p> : <div className="case-list">{similar.cases.map(c => <article className="case" key={c.case_enquiry_id}><div><strong>{c.neighborhood}</strong><span>{days(c.resolution_days)}</span></div><p>{c.closure_reason || "No closure note available."}</p><small>Case {c.case_enquiry_id} · Closed {c.closed_dt.slice(0, 10)} · {c.match_level === "same_neighborhood_season" ? "Same neighborhood and season" : c.match_level === "any_neighborhood_season" ? "Similar season, across Boston" : "Across Boston and seasons"}</small></article>)}</div>}
      </section>}
      <section className="context"><div><p className="eyebrow">THE CONTEXT MATTERS</p><h2>An estimate, with the full picture.</h2></div><div><p>These are historical estimates, not official deadlines or guarantees. Queue conditions reflect {result?.state_time.slice(0, 10) || "2025-10-01"}, before Boston’s 311 system change; they do not reflect today’s live backlog.</p><p>Only closed cases inform these estimates. About 25% of 2025 requests remained unclosed in the data, so actual waits may be longer. The city target shown is an estimate derived from historical records.</p></div></section>
    </main><footer><span className="brand">civic<span>pulse</span></span><p>Independent project · Not an official City of Boston service<br />Data: City of Boston 311, 2021–2025 · PDDL</p><a href="https://www.boston.gov/departments/boston-311">Visit Boston 311 ↗</a></footer>
  </>;
}
