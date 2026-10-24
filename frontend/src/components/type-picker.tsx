"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Meta, MetaType } from "@/types";

/* everyday words residents type -> words found in official type names */
const ALIAS: Record<string, string> = {
  rat: "rodent", rats: "rodent", mice: "rodent mice", mouse: "rodent mice", garbage: "trash", rubbish: "trash",
  bin: "trash barrel cart", barrel: "trash", car: "vehicle parking", cars: "vehicle parking", truck: "vehicle",
  road: "pothole roadway", street: "street pothole", hole: "pothole", lamp: "light", streetlight: "street light",
  loud: "noise", music: "noise parties", party: "parties", syringe: "needle", sharps: "needle", snow: "snow shovel",
  ice: "snow shovel", plow: "snow plowing", bug: "bed bugs pest", bugs: "bed bugs pest", cockroach: "pest",
  heat: "heat", mold: "mold dampness", dog: "animal", cat: "animal", bike: "bicycle", sign: "sign", tag: "graffiti",
  tree: "tree", leak: "utilities plumbing", water: "water hydrant catchbasin", drain: "catchbasin",
  homeless: "encampments", tent: "encampments", dumping: "dumping", couch: "bulk item", mattress: "mattress",
};

/** 2 = type name matches (directly or via an everyday word), 1 = only its category matches, 0 = no match */
function score(t: MetaType, group: string, q: string) {
  let qs = [q];
  if (q.length > 3 && q.endsWith("s")) qs.push(q.slice(0, -1));
  if (ALIAS[q]) qs = qs.concat(ALIAS[q].split(" "));
  const name = t.type.toLowerCase();
  if (qs.some(s => name.includes(s))) return 2;
  return group.toLowerCase().includes(q) ? 1 : 0;
}

type View = { kind: "cats" } | { kind: "group"; index: number };

export function TypePicker({ meta, value, onChange }: { meta: Meta; value: string; onChange: (t: string) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>({ kind: "cats" });
  const search = useRef<HTMLInputElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const byType = useMemo(() => Object.fromEntries(meta.types.map(t => [t.type, t])), [meta]);
  const groups = useMemo(() => meta.groups.map((name, i) => ({ name, index: i, types: meta.types.filter(t => t.group === i).sort((a, b) => b.n - a.n) })).filter(g => g.types.length), [meta]);
  const current = byType[value];

  useEffect(() => { if (open) search.current?.focus(); }, [open]);

  function toggle(next: boolean) {
    setOpen(next);
    if (next) { setQuery(""); setView({ kind: "cats" }); }
  }
  function choose(t: string) { onChange(t); toggle(false); button.current?.focus(); }

  const q = query.trim().toLowerCase();
  const hits = q ? meta.types.map(t => ({ t, s: score(t, meta.groups[t.group], q) })).filter(x => x.s > 0).sort((a, b) => b.s - a.s || b.t.n - a.t.n).map(x => x.t) : [];

  const typeButton = (t: MetaType, showGroup: boolean) => (
    <button type="button" key={t.type} className={t.type === value ? "sel" : undefined} onClick={() => choose(t.type)}>
      <span>{t.type}{showGroup && <small style={{ display: "block" }}>{meta.groups[t.group]}</small>}</span><small>{t.n.toLocaleString()}</small>
    </button>
  );

  return <>
    <button type="button" ref={button} className="pick" aria-expanded={open} aria-controls="picker" onClick={() => toggle(!open)}>
      {value}{current && <small>{meta.groups[current.group]} · {current.n.toLocaleString()} past requests</small>}
    </button>
    {open && <div className="panel" id="picker" onKeyDown={e => { if (e.key === "Escape") { toggle(false); button.current?.focus(); } }}>
      <input ref={search} type="search" placeholder="Search, e.g. pothole, rats, noise" aria-label="Search request types" autoComplete="off"
        value={query} onChange={e => setQuery(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); if (hits[0]) choose(hits[0].type); } }} />
      {q ? <>
        <div className="pk-h"><span>{hits.length} match{hits.length === 1 ? "" : "es"}</span><span>past requests</span></div>
        {hits.length ? <div className="tlist">{hits.map(t => typeButton(t, true))}</div> : <p className="note">No request type matches. Try a simpler word, or browse the categories.</p>}
      </> : view.kind === "group" ? <>
        <div className="pk-h"><button type="button" className="pk-back" onClick={() => setView({ kind: "cats" })}>← All categories</button><span>past requests</span></div>
        <h3 style={{ margin: "0 0 8px" }}>{meta.groups[view.index]}</h3>
        <div className="tlist">{groups.find(g => g.index === view.index)?.types.map(t => typeButton(t, false))}</div>
      </> : <>
        <div className="pk-h"><span>Featured</span></div>
        <div className="feat">{meta.types.filter(t => t.demo).map(t => <button type="button" key={t.type} onClick={() => choose(t.type)}>{t.type}</button>)}</div>
        <div className="pk-h"><span>Browse by category</span></div>
        <div className="cats">{groups.map(g => <button type="button" key={g.index} onClick={() => setView({ kind: "group", index: g.index })}>{g.name}<small>{g.types.length} type{g.types.length === 1 ? "" : "s"}</small></button>)}</div>
      </>}
    </div>}
  </>;
}
