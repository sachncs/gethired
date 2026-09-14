import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

const items = [
  {
    title: "Grounded in the master",
    body: "Every rewrite carries a citation to a verbatim span in your master resume. The grounding validator refuses output that can't be traced back.",
    accent: "from-accent-500/30 to-transparent",
  },
  {
    title: "Voice-preserving",
    body: "A per-master voice fingerprint — average bullet length, opening verbs, punctuation density — keeps the rewrite sounding like you, not like a chatbot.",
    accent: "from-emerald-400/30 to-transparent",
  },
  {
    title: "ATS-grade output",
    body: "12 deterministic gates run after every run: 9 hard-blocking (PDF compiles, headings, no tables, font size, page length) and 3 advisory. A failed hard gate blocks the run.",
    accent: "from-sky-400/30 to-transparent",
  },
  {
    title: "Anti-AI, anti-plagiarism",
    body: "Banned-word lists with verb-stem matching, parallelism detection, and 5-gram overlap checks against the JD corpus with a curated allowlist for common jargon.",
    accent: "from-rose-400/30 to-transparent",
  },
];

export function Pillars() {
  return (
    <section id="features" className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">Why gethired</span>
          <h2 className="display mt-3 text-[34px] leading-[1.05] sm:text-[48px]">
            Built to be <span className="gradient-text">honest</span>, not impressive.
          </h2>
          <p className="mt-5 text-[16px] sm:text-[17px] text-ink-600 dark:text-ink-300">
            Most tailoring tools optimise for sounding polished. gethired
            optimises for being true — every word can be traced, every claim
            is verifiable, every output clears the gates an applicant
            tracking system will actually run.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {items.map((it, i) => (
            <motion.div
              key={it.title}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] }}
              className="group relative overflow-hidden rounded-2xl surface p-7 transition hover:-translate-y-[2px] hover:shadow-soft"
            >
              <div
                className={`pointer-events-none absolute -inset-px -z-10 opacity-0 group-hover:opacity-100 transition duration-500 bg-gradient-to-br ${it.accent}`}
              />
              <div className="flex items-start justify-between">
                <h3 className="text-[19px] font-semibold tracking-tight">
                  {it.title}
                </h3>
                <ArrowRight className="h-4 w-4 -translate-x-1 opacity-0 transition group-hover:translate-x-0 group-hover:opacity-100 text-ink-400" />
              </div>
              <p className="mt-3 text-[14.5px] leading-relaxed text-ink-600 dark:text-ink-300">
                {it.body}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}