/* Static "How it works & limits" page. All numbers come from this repository's pipeline
   (reports/metrics.json, reports/equity.csv, models/app_accuracy.json). */
const IMP: [string, number][] = [["Request type", .211], ["City target time", .078], ["Recent speed, citywide", .046], ["Recent speed, neighborhood", .034], ["Time of day", .032], ["Weekday", .016], ["Recent slow cases", .013], ["How it was filed", .012], ["Requests waiting (90 days)", .010], ["Neighborhood", .004]];

function ImpRow({ name, v }: { name: string; v: number }) {
  return <><span>{name}</span><span><i style={{ width: `${(v / IMP[0][1]) * 100}%` }} /></span><span>{v.toFixed(3)}</span></>;
}

export function InfoPage() {
  return <div className="page info on" id="p-info">
<header className="sechead"><div className="w"><div className="eyebrow">CIVICPULSE</div><h1 style={{ fontSize: "clamp(30px,5vw,52px)" }}>How it works &amp; limits</h1></div></header>
<div className="w">

<section id="i-build">
  <h2>How we built it</h2><p className="sub">From raw city records to an estimate, in four steps.</p>
  <div className="flow">
    <div className="card"><b>01 · COLLECT</b><strong>1,433,236</strong><p>Boston 311 requests filed 2021–2025 (City of Boston open data).</p></div>
    <div className="card"><b>02 · CLEAN</b><strong>1,099,534</strong><p>Closed requests kept. We set aside 164,532 closures that were duplicates, invalid, automatic, referred elsewhere or mass clean-ups of old cases, and 169,170 that never closed.</p></div>
    <div className="card"><b>03 · LEARN</b><strong>2022–2023</strong><p>A gradient-boosted model learns the typical and the longer wait from what is known when a request is filed.</p></div>
    <div className="card"><b>04 · CHECK</b><strong>2025</strong><p>Tuned on 2024, then tested once on 2025 requests it never saw. No future information is used.</p></div>
  </div>
  <p className="note" style={{ marginTop: "14px" }}>Inputs the model uses: request type, neighborhood, how it was filed, time of day, weekday, holidays, the city's target time, how many similar requests were waiting, and how fast similar requests closed in the previous 30 days.</p>
</section>

<section id="i-read">
  <h2>How to read the numbers</h2><p className="sub">Two numbers, because waits are uneven.</p>
  <div className="two">
    <div className="card"><h3>Typical wait</h3><p className="note" style={{ fontSize: "14px" }}>The median: half of similar requests closed faster, half took longer.</p>
      <h3 style={{ marginTop: "16px" }}>Allow longer</h3><p className="note" style={{ fontSize: "14px" }}>The 80th percentile: 8 in 10 similar requests were done by then. Plan around this one if timing matters.</p></div>
    <div className="card"><h3>Why the gap can be large</h3><p className="note" style={{ fontSize: "14px", marginBottom: "22px" }}>Street light outages, all of Boston: many are fixed within a day, but over a third take more than a month. The typical wait sits in between, so look at the chart under your estimate.</p>
      <div className="mini" aria-hidden="true"><div style={{ height: "95%" }}><span>35%</span></div><div style={{ height: "14%" }}><span>5%</span></div><div style={{ height: "14%" }}><span>5%</span></div><div style={{ height: "11%" }}><span>4%</span></div><div style={{ height: "16%" }}><span>6%</span></div><div style={{ height: "24%" }}><span>9%</span></div><div style={{ height: "100%" }}><span>37%</span></div></div>
      <div className="minil" aria-hidden="true"><span>&lt;1d</span><span>1–2d</span><span>2–4d</span><span>4–7d</span><span>1–2w</span><span>2–4w</span><span>30d+</span></div>
      <p className="note">Share of closed street light outage requests by time to close: 35% under a day, 37% over 30 days.</p></div>
  </div>
</section>

<section id="i-acc">
  <h2>How accurate is it?</h2><p className="sub">Tested on 196,534 requests closed from 2025 filings, which the model never saw.</p>
  <div className="two">
    <div className="card">
      <div className="kv"><span>Average error, typical wait</span><span>7.84 days</span></div>
      <div className="kv"><span>Same, using past averages only</span><span>8.69 days</span></div>
      <div className="kv"><span>Median error</span><span>0.27 days (vs 0.34)</span></div>
      <div className="kv"><span>Done within "Allow longer"</span><span>83% (aim: 80%)</span></div>
      <p className="note">The improvement over past averages holds in a bootstrap check (95% interval: 0.81 to 0.89 days better). Averages are pulled up by a few very long cases; for most requests the error is small. "Done within" counts requests that closed; 25% of 2025 requests never closed in the data.</p>
    </div>
    <div className="card tw"><table>
      <thead><tr><th>Featured type</th><th>Avg error, model</th><th>Past averages</th><th>Done within "Allow longer"</th></tr></thead>
      <tbody>
        <tr><td>Pothole repair</td><td>5.01 d</td><td>5.20 d</td><td>86%</td></tr>
        <tr><td>Street light outage</td><td>29.41 d</td><td>30.29 d</td><td>92%</td></tr>
        <tr><td>Missed trash / recycling</td><td>0.28 d</td><td>0.41 d</td><td>78%</td></tr>
        <tr><td>Abandoned vehicle</td><td>15.23 d</td><td>23.92 d</td><td>98%</td></tr>
        <tr><td>Rodent activity</td><td>1.25 d</td><td>1.44 d</td><td>84%</td></tr>
      </tbody></table>
      <p className="note">The "chance of meeting the city target" is shown only for these five types: an earlier version was unreliable on 2025 data for other types (mainly parking enforcement, whose on-time rate fell from 46% to 24%).</p></div>
  </div>
</section>

<section id="i-drivers">
  <h2>What affects your wait</h2><p className="sub">How much the model's error grows when each input is scrambled, across all 2025 test requests. Longer bar, more influence.</p>
  <div className="card"><div className="imp">{IMP.map(([name, v]) => <ImpRow key={name} name={name} v={v} />)}</div>
  <p className="note">These are overall patterns, not the reason a specific request was slow.</p></div>
</section>

<section id="i-limits">
  <h2>Limits you should know</h2>
  <ul style={{ maxWidth: "720px" }}>
    <li><b>Some requests never close.</b> About 25% of 2025 requests (and about 32% of pothole requests every year) were still open in the data. Estimates use closed requests, so real waits can be longer. When this applies to your type, the estimate says so.</li>
    <li><b>The data stops in late 2025.</b> Boston changed its 311 system in October 2025; after that, closures stop appearing for some services (street light closures went from 279 in September to 1 in December). Queue conditions are taken from October 1, 2025.</li>
    <li><b>Same type, different jobs.</b> A burnt-out bulb and a knocked-down pole are both "street light outage". The model cannot see the size of the job.</li>
    <li><b>Reporting habits differ.</b> Areas and groups that report more appear more in the data; city staff also log many requests themselves, and those close much faster.</li>
    <li><b>Not official.</b> These are historical estimates, not City of Boston deadlines or promises.</li>
  </ul>
</section>

<section id="i-nbhd">
  <h2>Do neighborhoods wait longer?</h2><p className="sub">We trained a version of the model without any neighborhood information and compared its estimates with what happened in 2025.</p>
  <div className="two">
    <div className="card"><h3>Typical request</h3><p className="note" style={{ fontSize: "14px" }}>No meaningful gap. In every neighborhood the typical request closed within about 0.1 day (2.4 hours) of the estimate.</p>
      <h3 style={{ marginTop: "16px" }}>Long-running requests</h3><p className="note" style={{ fontSize: "14px" }}>Gaps appear among the slow cases. On average, requests ran past the estimate by 3.0 days citywide, from 1.4 days (East Boston, Hyde Park) to 6.1 days (West Roxbury).</p></div>
    <div className="card"><div className="kv"><span>West Roxbury</span><span>+6.1 d</span></div><div className="kv"><span>Charlestown</span><span>+5.5 d</span></div><div className="kv"><span>Roslindale</span><span>+4.7 d</span></div><div className="kv"><span>Citywide</span><span>+3.0 d</span></div><div className="kv"><span>Allston / Brighton</span><span>+1.9 d</span></div><div className="kv"><span>Hyde Park</span><span>+1.4 d</span></div><div className="kv"><span>East Boston</span><span>+1.4 d</span></div>
      <p className="note">Average days past the estimate, 2025 requests. Compare with the citywide line, not with zero: an estimate of the typical wait is passed by long cases everywhere.</p></div>
  </div>
  <p className="note" style={{ maxWidth: "720px" }}>This is a gap not explained by request type, timing and workload. It is not evidence of discrimination and does not show a cause. Unclosed requests (17% to 36% by neighborhood in 2025) and reporting habits can create or hide gaps.</p>
</section>

<section id="i-faq">
  <h2>Questions</h2>
  <div style={{ maxWidth: "720px" }}>
    <details><summary>Why is "Allow longer" so much longer than the typical wait?</summary><p>For some services a large share of requests wait weeks. The 80th percentile lands inside that slower group, so it can be many times the median. The chart under your estimate shows the spread.</p></details>
    <details><summary>Why does filing on a weekend change the estimate?</summary><p>Many crews work weekdays, so weekend requests often wait until Monday. A pothole filed on a Saturday has a typical wait about three times longer than one filed on a Monday.</p></details>
    <details><summary>Is this an official deadline?</summary><p>No. It is an independent estimate from past City of Boston 311 data. The city's own target time is shown separately when it exists.</p></details>
    <details><summary>Why are some similar cases from other neighborhoods?</summary><p>When there are few past requests of your type nearby, we show cases from across Boston and label them. "Most relevant" puts the same season and cases from before the October 2025 system change first.</p></details>
    <details><summary>Does this page save what I enter?</summary><p>No. Nothing is stored in your browser. When the prediction service is connected, only the request type, neighborhood and date are sent to it to compute the estimate.</p></details>
  </div>
</section>

<section id="i-data">
  <h2>Data &amp; privacy</h2>
  <ul style={{ maxWidth: "720px" }}>
    <li><b>Source:</b> City of Boston 311 Service Requests, 2021–2025, data.boston.gov, Public Domain Dedication and License (PDDL).</li>
    <li><b>Location:</b> neighborhood level only; no addresses or coordinates are used or shown.</li>
    <li><b>Closure notes:</b> shown as recorded by the city, shortened, with email addresses and phone numbers removed.</li>
    <li><b>Independent project:</b> built for BU Spark! DS+X 2026; not affiliated with the City of Boston.</li>
  </ul>
</section>

</div>
  </div>;
}
