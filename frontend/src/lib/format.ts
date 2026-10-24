import { useEffect, useState } from "react";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function bostonNow() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date());
  const get = (key: string) => parts.find(p => p.type === key)?.value;
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

export function days(n: number | null | undefined) {
  if (n === null || n === undefined) return "Not available";
  if (n < 1) { const h = Math.round(n * 24); return n * 24 < 1 ? "under 1 hour" : `about ${h} hour${h === 1 ? "" : "s"}`; }
  const r = Math.round(n * 10) / 10;
  return `${r.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${r === 1 ? "day" : "days"}`;
}

export const pct = (v: number) => `${Math.round(v * 100)}%`;
export const count = (v: number) => Math.round(v).toLocaleString();

/** Monday = 0, from a "YYYY-MM-DDTHH:MM" Boston wall-clock string. */
export function weekdayOf(local: string) {
  const m = local.match(/^(\d+)-(\d+)-(\d+)/);
  return m ? (new Date(+m[1], +m[2] - 1, +m[3]).getDay() + 6) % 7 : 0;
}

/** Ease-out count-up from 0 to `to` whenever `key` changes. */
export function useCountUp(to: number | null, ms = 1000, key: unknown = to) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (to === null) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setValue(to); return; }
    let frame = 0; let start: number | null = null;
    const step = (t: number) => {
      start ??= t;
      const p = Math.min((t - start) / ms, 1);
      setValue(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [key, to, ms]);
  return value;
}
