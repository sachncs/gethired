import { motion } from "framer-motion";
import { useEffect, useState } from "react";

type Line =
  | { kind: "prompt"; text: string }
  | { kind: "ok"; text: string }
  | { kind: "info"; text: string }
  | { kind: "dim"; text: string };

const sequences: { title: string; cmd: string; lines: Line[] }[] = [
  {
    title: "ingest",
    cmd: "gethired ingest sample.tex",
    lines: [
      { kind: "info", text: "▸ parsed master · 4 sections · 6 skills · 3 jobs · 2 projects" },
      { kind: "ok", text: "✓ wrote data/resume.json" },
    ],
  },
  {
    title: "run",
    cmd: "gethired run https://jobs.example.com/senior-platform-engineer",
    lines: [
      { kind: "info", text: "▸ fetched JD · senior platform engineer · Acme Corp" },
      { kind: "info", text: "▸ profiled voice · 14.2 avg bullet · 8 openers" },
      { kind: "info", text: "▸ wrote tailored · grounded · 6 citations" },
      { kind: "info", text: "▸ critic: grounding · style · plagiarism · ATS (12/12 pass)" },
      { kind: "ok", text: "✓ render → tailored/run-7f3a/tailored.pdf" },
    ],
  },
  {
    title: "cover",
    cmd: "gethired cover https://jobs.example.com/a https://jobs.example.com/b",
    lines: [
      { kind: "info", text: "▸ merged JD universe · 2 URLs · LLM-backed" },
      { kind: "info", text: "▸ wrote 2 cover letters · one per JD" },
      { kind: "ok", text: "✓ tailored/run-7f3a/cover_letter_0_senior-platform-engineer.md" },
      { kind: "ok", text: "✓ tailored/run-7f3a/cover_letter_1_staff-backend-engineer.md" },
    ],
  },
  {
    title: "audit",
    cmd: "gethired audit tailored/run-7f3a",
    lines: [
      { kind: "info", text: "▸ re-running grounding · style · plagiarism · ats" },
      { kind: "info", text: "▸ hard: 9/9 · advisory: 3/3 · skipped: 0" },
      { kind: "ok", text: "✓ wrote audit.json + audit.md" },
    ],
  },
];

export function Cli() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setActive((i) => (i + 1) % sequences.length);
    }, 5200);
    return () => window.clearInterval(id);
  }, []);

  const seq = sequences[active];

  return (
    <section id="cli" className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">The CLI surface</span>
          <h2 className="display mt-3 text-[34px] leading-[1.05] sm:text-[48px]">
            One verb at a time.
            <br />
            <span className="gradient-text">Scriptable end-to-end.</span>
          </h2>
          <p className="mt-5 text-[16px] sm:text-[17px] text-ink-600 dark:text-ink-300">
            Every command is single-purpose, flags are stable, and the same
            <code className="font-mono text-[13.5px] mx-1 rounded bg-ink-100 dark:bg-ink-800 px-1.5 py-0.5">Tailor</code>
            class powers both the CLI and the Python API.
          </p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-4">
          {sequences.map((s, i) => (
            <button
              key={s.title}
              onClick={() => setActive(i)}
              className={`rounded-xl border hairline px-4 py-3 text-left transition ${
                i === active
                  ? "bg-white dark:bg-ink-900 shadow-soft"
                  : "bg-white/40 dark:bg-ink-900/40 hover:bg-white/70 dark:hover:bg-ink-900/70"
              }`}
            >
              <div className="font-mono text-[12px] text-ink-500 dark:text-ink-400">gethired</div>
              <div className="mt-0.5 text-[15px] font-semibold tracking-tight">{s.title}</div>
            </button>
          ))}
        </div>

        <motion.div
          key={active}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mt-6 overflow-hidden rounded-2xl border border-ink-800 bg-ink-950 text-ink-100 shadow-soft"
        >
          <div className="flex items-center gap-2 border-b border-ink-800 px-4 py-3">
            <div className="flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-ink-700" />
              <span className="h-2.5 w-2.5 rounded-full bg-ink-700" />
              <span className="h-2.5 w-2.5 rounded-full bg-ink-700" />
            </div>
            <div className="ml-3 font-mono text-[12px] text-ink-400">~/projects/gethired</div>
          </div>
          <div className="p-6 font-mono text-[13px] leading-relaxed">
            <div>
              <span className="text-accent-300">$</span>{" "}
              <span className="text-ink-50">{seq.cmd}</span>
            </div>
            {seq.lines.map((l, i) => (
              <div key={i} className="mt-1.5">
                <LineRender line={l} />
              </div>
            ))}
          </div>
        </motion.div>

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Footnote k="Anti-bot recovery" v="WAF-blocked JDs auto-prompt for a paste, with a recovery command on no-TTY." />
          <Footnote k="Paste fallback" v="--pasted-jd <file> or --pasted-jd - skips the fetcher entirely." />
          <Footnote k="Streaming output" v="ProgressEvent callbacks emit as the pipeline runs." />
        </div>
      </div>
    </section>
  );
}

function LineRender({ line }: { line: Line }) {
  if (line.kind === "ok")
    return (
      <span className="text-emerald-400/90">
        <span className="text-emerald-500">✓</span> {line.text}
      </span>
    );
  if (line.kind === "info")
    return (
      <span className="text-ink-300">
        <span className="text-accent-300">●</span> {line.text}
      </span>
    );
  if (line.kind === "dim") return <span className="text-ink-500">{line.text}</span>;
  return (
    <span className="text-accent-200">
      <span className="text-accent-300">$</span> {line.text}
    </span>
  );
}

function Footnote({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-xl surface p-4">
      <div className="text-[12px] font-semibold uppercase tracking-wider text-ink-500 dark:text-ink-400">
        {k}
      </div>
      <p className="mt-1 text-[13.5px] text-ink-700 dark:text-ink-200">{v}</p>
    </div>
  );
}