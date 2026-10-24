"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { days } from "@/lib/format";
import { useInfo } from "@/components/result-card";
import type { CaseScope, CaseSort, CasesPage, EstimateRequest } from "@/types";

const SORTS: { key: CaseSort; label: string }[] = [
  { key: "rel", label: "Most relevant" }, { key: "recent", label: "Most recent" }, { key: "old", label: "Oldest" },
  { key: "short", label: "Shortest" }, { key: "long", label: "Longest" },
];

function pageButtons(page: number, pages: number) {
  const set = new Set([1, pages]);
  for (let k = page - 1; k <= page + 3; k++) if (k >= 1 && k <= pages) set.add(k);
  return [...set].sort((a, b) => a - b);
}

export function SimilarCases({ request, initial }: { request: EstimateRequest; initial: CasesPage | null }) {
  const [sort, setSort] = useState<CaseSort>("rel");
  const [scope, setScope] = useState<CaseScope>("nb");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CasesPage | null>(initial);
  const [error, setError] = useState(initial ? "" : "");
  const card = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  const info = useInfo("About similar requests", "Real closed requests of the same type, 2021–2025. \"Most relevant\" shows the same season and cases from before the October 2025 system change first. Blue marks the fastest 10% in this view. Closure notes are shortened; contact details are removed.");

  useEffect(() => {
    if (first.current && initial) { first.current = false; return; }
    first.current = false;
    let live = true;
    api<CasesPage>("cases", { ...request, sort, scope, page })
      .then(d => { if (live) { setData(d); setError(""); } })
      .catch(() => { if (live) setError("Historical cases are temporarily unavailable."); });
    return () => { live = false; };
  }, [request, sort, scope, page, initial]);

  function goTo(p: number) { setPage(p); card.current?.scrollIntoView({ behavior: "smooth" }); }

  return <div className="card" id="simcard" ref={card} style={{ marginTop: 20 }}>
    <h3>Similar past requests{info.button}</h3>{info.text}
    <div className="flt">
      {SORTS.map(s => <button type="button" key={s.key} className={sort === s.key ? "on" : undefined} onClick={() => { setSort(s.key); setPage(1); }}>{s.label}</button>)}
      <select aria-label="Scope" value={scope} onChange={e => { setScope(e.target.value as CaseScope); setPage(1); }}><option value="nb">This neighborhood</option><option value="all">All of Boston</option></select>
    </div>
    {error ? <p className="note">{error}</p> : !data ? <p className="note">Loading cases…</p> : !data.available ? <p className="note">{data.message} Your estimate is available independently.</p> : <>
      <p className="note" style={{ margin: "0 0 6px" }}>{data.total.toLocaleString()} closed requests · page {data.page.toLocaleString()} of {data.pages.toLocaleString()}</p>
      <div>{data.cases.length === 0 ? <p className="note">No cases found for this selection. Try &quot;All of Boston&quot;.</p> : data.cases.map((c, i) => {
        const open = c.open_dt.slice(0, 10), closed = c.closed_dt.slice(0, 10);
        const label = (c.same_neighborhood ? "Same neighborhood" : "Across Boston")
          + (c.same_season ? (c.same_neighborhood ? " and season" : ", similar season") : (c.same_neighborhood ? ", other season" : ""))
          + (c.after_system_change ? " · after Oct 2025 system change" : "");
        return <div className={c.fastest ? "case top" : "case"} style={{ ["--i" as string]: i }} key={`${data.page}-${c.case_enquiry_id}`}>
          <div><b>{c.neighborhood}{c.fastest && <span className="chip">Fastest 10%</span>}</b><p>{c.closure_reason || "No closure note recorded."}</p><small>Case {c.case_enquiry_id} · {label}</small></div>
          <div className="r"><span className="d">{days(c.resolution_days)}</span><span className="dt">Opened {open}</span><span className="dt">Closed {closed}</span></div>
        </div>;
      })}</div>
      {data.pages > 1 && <div className="pg">
        <button type="button" aria-label="Previous page" disabled={data.page <= 1} onClick={() => goTo(data.page - 1)}>‹</button>
        {pageButtons(data.page, data.pages).map((k, i, arr) => <span key={k} style={{ display: "contents" }}>
          {i > 0 && k - arr[i - 1] > 1 && <span>…</span>}
          <button type="button" className={k === data.page ? "on" : undefined} onClick={() => goTo(k)}>{k.toLocaleString()}</button>
        </span>)}
        <button type="button" aria-label="Next page" disabled={data.page >= data.pages} onClick={() => goTo(data.page + 1)}>›</button>
      </div>}
    </>}
  </div>;
}
