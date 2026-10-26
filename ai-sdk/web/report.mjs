import { readFile } from "node:fs/promises";
const rows = (
  await readFile(process.argv[2] || ".voice-data/events.jsonl", "utf8")
)
  .trim()
  .split("\n")
  .filter(Boolean)
  .map(JSON.parse);
const counts = {};
for (const row of rows) {
  const source = row.source || "direct";
  counts[source] ??= {};
  counts[source][row.event] ??= new Set();
  counts[source][row.event].add(row.session);
}
console.log(
  JSON.stringify(
    {
      unit: "unique demo sessions, not people or paid customers",
      sources: Object.fromEntries(
        Object.entries(counts).map(([s, events]) => [
          s,
          Object.fromEntries(
            Object.entries(events).map(([e, ids]) => [e, ids.size]),
          ),
        ]),
      ),
      limitations:
        "Signup and pricing clicks are intent only. Signup completion, account activation, retention and payment require server-side Console/billing events joined with a consented campaign identifier. This reference app does not claim to measure those.",
    },
    null,
    2,
  ),
);
