"use client";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { EstimateNotes } from "@/components/estimate-notes";
import type { Choices, Prediction, SimilarCase, SimilarResult, EstimateRequest } from "@/types";

function bostonNow() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date());
  const get = (key: string) => parts.find(p => p.type === key)?.value;
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}
function days(n: number | null) {
  if (n === null) return "Not available";
  if (n < 1) { const h = n * 24; return h < 1 ? "under 1 hour" : `about ${Math.round(h)} hours`; }
  const shown = n.toLocaleString(undefined, { maximumFractionDigits: 1 });
  return `${shown} ${shown === "1" ? "day" : "days"}`;
}
const SORTS: Record<string, { label: string; compare?: (a: SimilarCase, b: SimilarCase) => number }> = {
  match: { label: "Best match" },
  newest: { label: "Newest first", compare: (a, b) => b.closed_dt.localeCompare(a.closed_dt) },
  oldest: { label: "Oldest first", compare: (a, b) => a.closed_dt.localeCompare(b.closed_dt) },
  fastest: { label: "Shortest resolution", compare: (a, b) => a.resolution_days - b.resolution_days },
  slowest: { label: "Longest resolution", compare: (a, b) => b.resolution_days - a.resolution_days },
};
const sortCases = (cases: SimilarCase[], key: string) => { const compare = SORTS[key].compare; return compare ? [...cases].sort(compare) : cases; };
const matchLabel =(level: string) => level === "same_neighborhood_season" ? "Same neighborhood and season" : level === "any_neighborhood_season" ? "Similar season, across Boston" : "Across Boston and seasons";

function modelStatus(result: Prediction) {
  const ml = (used: string) => used === "ml" ? "prediction model" : "historical baseline";
  if (result.used_model === "ml" && result.p80_used_model === "ml") return <><b>Model estimate.</b> Both numbers come from the trained prediction model.</>;
  if (result.used_model !== "ml" && result.p80_used_model !== "ml") return <><b>Historical estimate.</b> Based on the per-type median and 80th percentile of past closed cases.</>;
  return <><b>Mixed estimate.</b> Typical wait: {ml(result.used_model)}. Longer estimate: {ml(result.p80_used_model)}.</>;
}

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
  const [sort, setSort] = useState("match");
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
    <header>
      <div className="bar"><a className="brand" href="/" aria-label="CivicPulse home">civic<b>pulse</b></a><div className="tag">BOSTON · 311</div></div>
      <div className="hero"><h1>Your request.<br />A clearer timeline.</h1><p>See how long similar Boston 311 requests have taken, based on past cases.</p></div>
    </header>
    <main>
      <div className="grid">
        <section className="card" aria-label="Request details">
          <div className="head"><span className="num">1</span><h2>Your request</h2></div>
          {choiceError ? <div role="alert" className="error">{choiceError}<button className="text-button" onClick={loadChoices}>Retry loading options</button></div> : !choices ? <p role="status" className="note">Loading request options…</p> :
          <form onSubmit={submit}><fieldset disabled={loading}>
            <label htmlFor="type">Request type</label><select id="type" value={type} onChange={e => setType(e.target.value)} required><optgroup label="Featured requests">{choices.types.filter(t => t.demo).map(t => <option key={t.type}>{t.type}</option>)}</optgroup><optgroup label="All other requests">{choices.types.filter(t => !t.demo).map(t => <option key={t.type}>{t.type}</option>)}</optgroup></select>
            <label htmlFor="neighborhood">Neighborhood</label><select id="neighborhood" value={neighborhood} onChange={e => setNeighborhood(e.target.value)} required>{choices.neighborhoods.map(n => <option key={n}>{n}</option>)}</select>
            <label htmlFor="date">Date and time</label><input id="date" type="datetime-local" value={date} onChange={e => setDate(e.target.value)} required /><p className="note">Boston time. Timing can affect the estimate.</p>
            <button className="go" disabled={!date || loading} type="submit">{loading ? "Calculating your estimate…" : "Estimate resolution time"}</button>
          </fieldset></form>}
          <p className="note">This tool does not submit a 311 request.</p>
        </section>
        <section className="card" aria-live="polite" aria-busy={loading} aria-label="Estimate">
          <div className="head"><span className="num">2</span><h2>Estimated timeline</h2></div>
          {error ? <div role="alert" className="error">{error}</div> : result ? <>
            <p className="note context-line">{submitted?.type} · {submitted?.neighborhood} · {submitted?.open_date.replace("T", " at ")} Eastern</p>
            <div className="metrics"><div className="m main"><p>Typical wait</p><strong>{days(result.p50)}</strong><small>Median</small></div><div className="m"><p>Allow longer</p><strong>{days(result.p80)}</strong><small>8 in 10 done by then</small></div></div>
            <div className="range" aria-hidden="true"><div className="track"><div className="fill" /></div><div className="ticks"><span>Request</span><span>Typical</span><span>8 in 10 done</span></div></div>
            <dl><div><dt>City target (estimated)</dt><dd>{days(result.target_days)}</dd></div><div><dt>Chance of meeting target</dt><dd>{result.p_ontime === null ? "Not available" : `${Math.round(result.p_ontime * 100)}%`}</dd></div><div><dt>Historical typical wait</dt><dd>{days(result.baseline_p50)}</dd></div><div><dt>Past cases of this type</dt><dd>{result.n_support.toLocaleString()}</dd></div></dl>
            <EstimateNotes notes={result.notes} />
          </> : <div className="empty"><div className={loading ? "ring spin" : "ring"} />{loading ? "Checking historical patterns for your request…" : "Choose your details and press the button to see an estimate."}</div>}
        </section>
      </div>
      <div className="status" role="status">{result ? modelStatus(result) : <><b>Real data.</b> Request types and neighborhoods come from the model files. Press the button to see an estimate.</>}</div>
      {result && <section className="card history"><div className="head"><span className="num">3</span><h2>Similar past requests</h2></div><p className="note context-line">Real closed cases, matched by request type, season, and neighborhood when possible.</p>
        {similarError ? <p role="status" className="note">{similarError}</p> : !similar ? <p className="note">Loading historical cases…</p> : !similar.available ? <p className="status">{similar.message} Your prediction is available independently.</p> : similar.cases.length === 0 ? <p className="note">No matching closed cases were found before this request date.</p> : <><div className="sort"><label htmlFor="sort">Sort by</label><select id="sort" value={sort} onChange={e => setSort(e.target.value)}>{Object.entries(SORTS).map(([key, s]) => <option key={key} value={key}>{s.label}</option>)}</select></div><div className={sort === "newest" || sort === "oldest" ? "case-list by-date" : "case-list"}>{sortCases(similar.cases, sort).map(c => <article className="case" key={c.case_enquiry_id}><div><strong>{c.neighborhood}</strong><span>{days(c.resolution_days)}</span></div><p>{c.closure_reason || "No closure note available."}</p><small>Case {c.case_enquiry_id} · <span className="closed">Closed {c.closed_dt.slice(0, 10)}</span> ·{matchLabel(c.match_level)}</small></article>)}</div></>}
      </section>}
      <section className="context">
        <div><h2>Good to know</h2><p>Estimates are historical, not official deadlines or guarantees. The city target shown is an estimate derived from historical records.</p></div>
        <div><h2>Limits</h2><p>Only closed cases are used, and about 25% of 2025 requests remained unclosed in the data, so real waits may be longer. Queue conditions are as of {result?.state_time.slice(0, 10) || "2025-10-01"}, before Boston’s 311 system change, not today’s live backlog.</p></div>
      </section>
    </main>
    <footer><p>Independent project · Not an official City of Boston service · Data: City of Boston 311, 2021–2025 (PDDL)</p><a href="https://www.boston.gov/departments/boston-311">Visit Boston 311 ↗</a></footer>
  </>;
}
