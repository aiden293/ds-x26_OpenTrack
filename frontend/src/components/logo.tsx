import { Inter } from "next/font/google";

const inter = Inter({ weight: "800", subsets: ["latin"], display: "swap" });

/* Heartbeat wordmark from design/logo/heartbeat.html: the two i's of "civic" are drawn as
   stems so the gold dots and the ECG line joining them can be placed exactly. */
function Stem({ ecg, stroke }: { ecg?: boolean; stroke: number }) {
  return <span className="wm-st">
    {ecg && <svg className="wm-ecg" viewBox="0 0 81 40" aria-hidden="true"><polyline points="0,20 27,20 33,20 38,5 45,35 51,12 55,20 81,20" fill="none" stroke="#E0B93A" strokeWidth={stroke} strokeLinejoin="round" strokeLinecap="round" /></svg>}
    <span className="wm-dot" />
  </span>;
}

export function Logo({ stroke = 5 }: { stroke?: number }) {
  return <span className={`wm ${inter.className}`} role="img" aria-label="CivicPulse">
    <span className="wm-tx" aria-hidden="true">c</span><Stem ecg stroke={stroke} /><span className="wm-vv" aria-hidden="true">v</span><Stem stroke={stroke} /><span className="wm-tx" aria-hidden="true">c</span><span className="wm-tx wm-pu" aria-hidden="true">pulse</span>
  </span>;
}
