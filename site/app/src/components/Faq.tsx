import { motion } from "framer-motion";

const faqs = [
  {
    q: "Does gethired invent experience to match the JD?",
    a: "No. Every rewritten bullet carries a GroundedCitation — a verbatim span from the master resume — and the grounding validator refuses output where the span cannot be traced back. Reframing language, surfacing relevant achievements, and aligning terminology is in scope; adding facts is not.",
  },
  {
    q: "Which LLMs are supported?",
    a: "Anthropic native, OpenAI native, and any Anthropic-API-compatible platform. Set MODEL=MiniMax-M3 and BASE_URL and the provider layer routes automatically. Tests inject a Pydantic AI TestModel for deterministic runs.",
  },
  {
    q: "What does the ATS contract actually verify?",
    a: "12 tri-state gates. 9 hard-blocking gates — PDF compiles, PDF text extractable, PDF text matches .txt, standard section headings, no layout tables, no images, no colours, 10–12 pt font, length within page limit — block the run on failure. 3 advisory gates (keyword coverage, bullet quantification, action verbs) report but never block.",
  },
  {
    q: "Can I tailor against multiple JDs at once?",
    a: "Yes. gethired run accepts multiple URLs. They go through an LLM-backed merger that unions must-haves, intersects nice-to-haves, and reasons about seniority, role specificity, and responsibility overlap — not a naive bag of words.",
  },
  {
    q: "What if a JD is behind an anti-bot wall?",
    a: "The fetcher detects Cloudflare / AWS WAF (HTTP 403 with WAF markers), prints a recovery command, and — on a TTY — launches an inline paste prompt. --pasted-jd <file> (or --pasted-jd - for stdin) skips the fetcher entirely.",
  },
  {
    q: "How does voice preservation work?",
    a: "gethired.profiler.build() computes a per-master fingerprint — average bullet length, standard deviation, opening verbs, punctuation density, sentence count — and injects it into the writer prompt so the rewrite stays in your voice.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">FAQ</span>
          <h2 className="display mt-3 text-[32px] leading-[1.05] sm:text-[42px]">
            Honest answers.
          </h2>
          <p className="mt-4 text-[15.5px] sm:text-[17px] text-ink-600 dark:text-ink-300">
            The questions we get most often, answered without marketing.
          </p>
        </div>

        <div className="mx-auto mt-12 max-w-3xl divide-y divide-ink-200/70 dark:divide-ink-800/80 rounded-2xl surface">
          {faqs.map((f, i) => (
            <motion.details
              key={i}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.4, delay: i * 0.04 }}
              className="group p-6 sm:p-8 [&[open]]:bg-ink-50/60 dark:[&[open]]:bg-ink-900/40"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
                <span className="text-[16px] font-semibold tracking-tight text-ink-900 dark:text-white">
                  {f.q}
                </span>
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border hairline text-ink-500 dark:text-ink-400 transition group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="mt-4 max-w-2xl text-[14.5px] leading-relaxed text-ink-600 dark:text-ink-300">
                {f.a}
              </p>
            </motion.details>
          ))}
        </div>
      </div>
    </section>
  );
}