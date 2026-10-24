"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { bostonNow, count, useCountUp } from "@/lib/format";
import { TypePicker } from "@/components/type-picker";
import { ResultCard } from "@/components/result-card";
import { SimilarCases } from "@/components/similar-cases";
import { InfoPage } from "@/components/info-page";
import type { CasesPage, EstimateRequest, Insights, Meta, Prediction } from "@/types";

const MIN_LOADING_MS = 1300;

function Stat({ to, label, delayed }: { to: number; label: string; delayed: boolean }) {
  const v = useCountUp(delayed ? to : null, 1800);
  return <div><strong>{count(v)}</strong><span>{label}</span></div>;
}

/** Scroll progress bar + hero orb parallax, as in the prototype. */
function useScrollEffects() {
  const prog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let ticking = false;
    const onScroll = () => {
      if (ticking) return; ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY, h = document.documentElement.scrollHeight - window.innerHeight;
        if (prog.current) prog.current.style.width = `${h > 0 ? (y / h) * 100 : 0}%`;
        document.querySelectorAll<HTMLElement>(".orb").forEach(o => { o.style.transform = `translateY(${y * Number(o.dataset.p)}px)`; });
        ticking = false;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return prog;
}

type View = "form" | "load" | "res";

export default function Home() {
  const [tab, setTab] = useState<"est" | "info">("est");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState("");
  const [type, setType] = useState("Request for Pothole Repair");
  const [neighborhood, setNeighborhood] = useState("Dorchester");
  const [date, setDate] = useState("");
  const [view, setView] = useState<View>("form");
  const [request, setRequest] = useState<EstimateRequest | null>(null);
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const [insights, setInsights] = useState<Insights | null>(null);
  const [insightsError, setInsightsError] = useState("");
  const [cases, setCases] = useState<CasesPage | null>(null);
  const [statsOn, setStatsOn] = useState(false);
  const est = useRef<HTMLElement>(null);
  const prog = useScrollEffects();

  async function loadMeta() {
    setMetaError("");
    try {
      const m = await api<Meta>("meta"); setMeta(m);
      if (!m.types.some(t => t.type === type)) setType(m.types[0].type);
      if (!m.neighborhoods.includes(neighborhood)) setNeighborhood(m.neighborhoods[0]);
    } catch { setMetaError("We couldn’t load request options. Check that the API is running, then retry."); }
  }
  useEffect(() => {
    setDate(bostonNow()); void loadMeta();
    const t = setTimeout(() => setStatsOn(true), 700);
    return () => clearTimeout(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function show(v: View) { setView(v); est.current?.scrollIntoView({ behavior: "smooth" }); }
  function switchTab(t: "est" | "info") { setTab(t); window.scrollTo({ top: 0 }); }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const started = Date.now();
    const req = { type, neighborhood, open_date: date || bostonNow() };
    setRequest(req); setResult(null); setError(""); setInsights(null); setInsightsError(""); setCases(null);
    show("load");
    await Promise.all([
      api<Prediction>("predict", req).then(setResult).catch(e => setError(e.message)),
      api<Insights>("insights", req).then(setInsights).catch(e => setInsightsError(e.message)),
      api<CasesPage>("cases", { ...req, sort: "rel", scope: "nb", page: 1 }).then(setCases).catch(() => setCases(null)),
    ]);
    const left = MIN_LOADING_MS - (Date.now() - started);
    if (left > 0) await new Promise(r => setTimeout(r, left));
    show("res");
  }

  const s = meta?.stats;
  return <>
    <div id="prog" ref={prog} />
    <nav><div className="w"><span className="logo">civic<b>pulse</b></span><span>
      <button className={tab === "est" ? "tab on" : "tab"} onClick={() => switchTab("est")}>Estimate</button>
      <button className={tab === "info" ? "tab on" : "tab"} onClick={() => switchTab("info")}>How it works<span className="lg"> &amp; limits</span></button>
    </span></div></nav>

    {tab === "est" ? <div className="page on" id="p-est">
      <header className="hero">
        <div className="orb o1" data-p=".12" /><div className="orb o2" data-p="-.08" />
        <div className="w">
          <h1><span className="ln" style={{ ["--i" as string]: 1, display: "block" }}>Your request.</span><span className="ln" style={{ ["--i" as string]: 2, display: "block" }}>A clearer timeline.</span></h1>
          <p className="lead ln" style={{ ["--i" as string]: 3 }}>See how long Boston 311 requests like yours have really taken, built from 1.1 million closed requests filed 2021–2025.</p>
          <button className="btn ln" style={{ ["--i" as string]: 4 }} onClick={() => est.current?.scrollIntoView({ behavior: "smooth" })}>Estimate my wait</button>
          <div className="stats ln" style={{ ["--i" as string]: 5 }}>
            <Stat to={s?.cases ?? 0} label="closed requests analysed" delayed={statsOn && !!s} />
            <Stat to={s?.types ?? 0} label="request types" delayed={statsOn && !!s} />
            <Stat to={s?.neighborhoods ?? 0} label="neighborhoods" delayed={statsOn && !!s} />
            <Stat to={5} label={`years of data (${s?.years ?? "2021–2025"})`} delayed={statsOn} />
          </div>
        </div>
      </header>

      <section id="est" ref={est}><div className="w">
        {view === "form" && <div className="view on"><div className="fwrap">
          <h2>Find your estimate</h2><p className="sub">Pick what you reported, where, and when. No personal information needed.</p>
          <div className="card">
            {metaError ? <div role="alert" className="error">{metaError}<button className="text-button" onClick={loadMeta}>Retry loading options</button></div>
              : !meta ? <p role="status" className="note">Loading request options…</p>
              : <form onSubmit={submit}><fieldset>
                <label id="typeLbl">Request type</label>
                <TypePicker meta={meta} value={type} onChange={setType} />
                <label htmlFor="hood">Neighborhood</label>
                <select id="hood" value={neighborhood} onChange={e => setNeighborhood(e.target.value)}>{meta.neighborhoods.map(n => <option key={n}>{n}</option>)}</select>
                <label htmlFor="when">Date and time</label>
                <input id="when" type="datetime-local" value={date} onChange={e => setDate(e.target.value)} required />
                <p className="note">Boston time. The day of the week changes the estimate.</p>
                <button className="btn" type="submit">Estimate resolution time</button>
                <p className="note"><b>Disclosure:</b> This is only an estimate based on past 311 cases. It is not an official deadline or a guarantee. This tool does not submit a 311 request.</p>
              </fieldset></form>}
          </div>
        </div></div>}

        {view === "load" && <div className="view on" id="v-load" aria-live="polite"><div className="empty"><div className="ring" />Looking up past cases…</div></div>}

        {view === "res" && request && <div className="view on" id="v-res"><div className="rwrap">
          <button className="back" onClick={() => show("form")}>← New estimate</button>
          {error ? <div className="card"><div role="alert" className="error">{error}</div></div>
            : result && <ResultCard request={request} result={result} insights={insights} insightsError={insightsError} />}
          <SimilarCases request={request} initial={cases} />
        </div></div>}
      </div></section>
    </div> : <InfoPage />}

    <footer>Independent project · Not an official City of Boston service · Data: City of Boston 311 Service Requests 2021–2025, data.boston.gov (PDDL) · <a href="https://www.boston.gov/departments/boston-311" style={{ color: "#fff" }}>Visit Boston 311 ↗</a></footer>
  </>;
}
