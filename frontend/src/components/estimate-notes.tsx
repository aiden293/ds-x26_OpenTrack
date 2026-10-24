import type { Prediction } from "@/types";

export function EstimateNotes({ notes }: Pick<Prediction, "notes">) {
  // The shared context section already explains the queue snapshot.
  const requestNotes = (notes ?? []).filter(note => note.code !== "queue_snapshot");
  if (requestNotes.length === 0) return null;

  return (
    <section className="estimate-notes" aria-labelledby="estimate-notes-title">
      <h3 id="estimate-notes-title">What to keep in mind</h3>
      <ul>
        {requestNotes.map(note => <li key={note.code}>{note.message}</li>)}
      </ul>
    </section>
  );
}
