import type { Prediction } from "@/types";

export function EstimateNotes({ notes }: Pick<Prediction, "notes">) {
  // The footer and "How it works" page already explain the queue snapshot.
  const requestNotes = (notes ?? []).filter(note => note.code !== "queue_snapshot");
  if (requestNotes.length === 0) return null;

  return (
    <section className="watch" role="note" aria-labelledby="estimate-notes-title">
      <h3 id="estimate-notes-title">
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2 21h20L12 3z" fill="none" stroke="#b08400" strokeWidth="2" strokeLinejoin="round" /><path d="M12 10v5M12 18v.5" stroke="#b08400" strokeWidth="2" strokeLinecap="round" /></svg>
        What might affect your wait
      </h3>
      <ul>
        {requestNotes.map(note => <li key={note.code}>{note.message}</li>)}
      </ul>
    </section>
  );
}
