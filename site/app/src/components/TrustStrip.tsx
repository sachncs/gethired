import { motion } from "framer-motion";

const logos = [
  "Pydantic AI",
  "Anthropic",
  "OpenAI",
  "Typer",
  "Rich",
  "Trafilatura",
  "PyMuPDF",
  "Jinja2",
  "Loguru",
  "httpx",
  "tenacity",
  "PyYAML",
];

export function TrustStrip() {
  return (
    <section className="relative border-y hairline bg-ink-50/40 dark:bg-ink-950">
      <div className="container-x py-10">
        <div className="flex flex-col items-center gap-6 text-center sm:flex-row sm:justify-between sm:text-left">
          <div>
            <div className="eyebrow">Built on trusted foundations</div>
            <p className="mt-1 text-[14px] text-ink-600 dark:text-ink-300">
              A production-ready stack — fully typed, fully tested.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-end">
            <Pill>Python 3.12+</Pill>
            <Pill>PEP 695</Pill>
            <Pill>MIT</Pill>
            <Pill>303 tests</Pill>
            <Pill>Zero suppressions</Pill>
          </div>
        </div>

        <div className="mt-8 overflow-hidden scrollbar-none">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="flex w-max items-center gap-12 animate-marquee"
          >
            {[...logos, ...logos].map((l, i) => (
              <span
                key={`${l}-${i}`}
                className="text-[14px] font-semibold tracking-tight text-ink-400 dark:text-ink-500 whitespace-nowrap"
              >
                {l}
              </span>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="chip">
      <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
      {children}
    </span>
  );
}