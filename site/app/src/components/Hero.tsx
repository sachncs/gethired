import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Sparkles, Terminal } from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: 0.06 * i, duration: 0.6, ease: [0.22, 1, 0.36, 1] },
  }),
};

export function Hero() {
  return (
    <section id="top" className="relative isolate overflow-hidden pt-12 pb-20 sm:pt-20 sm:pb-28">
      {/* Background layers */}
      <div className="absolute inset-0 -z-10 bg-grid" aria-hidden />
      <div
        className="absolute inset-x-0 top-0 -z-10 h-[560px] ring-fade"
        aria-hidden
        style={{
          background:
            "radial-gradient(60% 50% at 50% 30%, rgba(124,92,255,0.18) 0%, rgba(124,92,255,0.06) 40%, transparent 70%)",
        }}
      />
      <div className="container-x">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={0}
          className="mx-auto flex max-w-3xl flex-col items-center text-center"
        >
          <span className="chip">
            <Sparkles className="h-3.5 w-3.5 text-accent-500" />
            Multi-agent · Grounded · ATS-verified
          </span>
        </motion.div>

        <motion.h1
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={1}
          className="display mx-auto mt-6 max-w-4xl text-center text-[44px] leading-[1.04] sm:text-[68px] sm:leading-[1.02] lg:text-[88px]"
        >
          Tailored resumes.
          <br />
          <span className="gradient-text">Grounded in truth.</span>
        </motion.h1>

        <motion.p
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={2}
          className="mx-auto mt-7 max-w-2xl text-center text-[17px] leading-relaxed text-ink-600 dark:text-ink-300 sm:text-[19px]"
        >
          gethired is a layered, multi-agent pipeline that rewrites your
          master resume against any job description — without fabrication,
          with 12-gate ATS verification, and a voice that still sounds like
          you.
        </motion.p>

        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={3}
          className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <a href="#install" className="btn-primary px-6 py-3 text-[14.5px]">
            <Terminal className="h-4 w-4" />
            Get started
            <ArrowRight className="h-4 w-4" />
          </a>
          <a
            href="https://github.com/sachncs/gethired"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost px-6 py-3 text-[14.5px]"
          >
            View on GitHub
          </a>
        </motion.div>

        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={4}
          className="mx-auto mt-8 flex max-w-xl flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[12.5px] text-ink-500 dark:text-ink-400"
        >
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-accent-500" />
            12 ATS gates
          </span>
          <span className="h-1 w-1 rounded-full bg-ink-300 dark:bg-ink-700" />
          <span>No fabrication</span>
          <span className="h-1 w-1 rounded-full bg-ink-300 dark:bg-ink-700" />
          <span>303 tests</span>
          <span className="h-1 w-1 rounded-full bg-ink-300 dark:bg-ink-700" />
          <span>MIT licensed</span>
        </motion.div>
      </div>

      {/* Showcase */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.45, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="container-x mt-16 sm:mt-20"
      >
        <HeroMockup />
      </motion.div>
    </section>
  );
}

function HeroMockup() {
  return (
    <div className="relative mx-auto max-w-5xl">
      <div
        className="absolute -inset-6 -z-10 rounded-[28px] opacity-70 blur-2xl"
        style={{
          background:
            "radial-gradient(60% 60% at 50% 50%, rgba(124,92,255,0.35), transparent 70%)",
        }}
      />
      <div className="surface-strong rounded-2xl overflow-hidden">
        <div className="flex items-center gap-2 border-b hairline bg-ink-50/60 dark:bg-ink-900/60 px-4 py-3">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-ink-300 dark:bg-ink-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-ink-300 dark:bg-ink-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-ink-300 dark:bg-ink-700" />
          </div>
          <div className="ml-3 hidden sm:flex items-center gap-2 text-[12px] text-ink-500 dark:text-ink-400">
            <Terminal className="h-3.5 w-3.5" />
            match_report.md · tailored/run-7f3a
          </div>
          <div className="ml-auto chip">ATS · PASS · 12/12</div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-12">
          {/* Left: terminal */}
          <div className="lg:col-span-7 p-5 sm:p-7 border-b lg:border-b-0 lg:border-r hairline bg-ink-950 text-ink-100">
            <div className="font-mono text-[12.5px] leading-relaxed">
              <div className="text-ink-400">$ gethired run https://jobs.example.com/senior-platform-engineer</div>
              <div className="mt-3 text-ink-300">
                <span className="text-accent-300">●</span> parsed master · sample.tex · 4 sections
              </div>
              <div className="text-ink-300">
                <span className="text-accent-300">●</span> fetched JD · senior platform engineer
              </div>
              <div className="text-ink-300">
                <span className="text-accent-300">●</span> profiled voice · 14.2 avg bullet · 8 openers
              </div>
              <div className="text-ink-300">
                <span className="text-accent-300">●</span> wrote tailored · grounded · 6 citations
              </div>
              <div className="text-ink-300">
                <span className="text-accent-300">●</span> critic: grounding · style · plagiarism · ATS
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Gate label="pdf_compiles" status="pass" />
                <Gate label="pdf_text_matches" status="pass" />
                <Gate label="headings_standard" status="pass" />
                <Gate label="no_tables" status="pass" />
                <Gate label="font_size" status="pass" />
                <Gate label="length_in_page" status="pass" />
              </div>
              <div className="mt-4 text-emerald-400/90">
                ✓ render → tailored/run-7f3a/tailored.pdf
              </div>
            </div>
          </div>
          {/* Right: report preview */}
          <div className="lg:col-span-5 p-5 sm:p-7">
            <div className="eyebrow">Match report</div>
            <h3 className="mt-2 text-[18px] font-semibold tracking-tight">
              Senior Platform Engineer
            </h3>
            <p className="mt-1 text-[13px] text-ink-500 dark:text-ink-400">
              Acme Corp · Remote · Full-time
            </p>
            <div className="mt-5 grid grid-cols-3 gap-3">
              <Stat label="Coverage" value="92%" />
              <Stat label="Citations" value="6" />
              <Stat label="Bullets" value="14" />
            </div>
            <div className="mt-5">
              <div className="eyebrow">Must-haves</div>
              <ul className="mt-2 space-y-1.5 text-[13.5px]">
                {[
                  "Distributed systems",
                  "Kubernetes",
                  "Postgres at scale",
                  "Mentorship",
                ].map((s) => (
                  <li key={s} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="mt-5 rounded-xl border hairline p-3 text-[12.5px] text-ink-600 dark:text-ink-300">
              <span className="text-ink-500 dark:text-ink-400">voice drift:</span>{" "}
              <span className="font-semibold text-emerald-500">0.04</span>{" "}
              <span className="text-ink-500 dark:text-ink-400">· below threshold 0.12</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Gate({ label, status }: { label: string; status: "pass" | "fail" | "skip" }) {
  const color =
    status === "pass"
      ? "text-emerald-400 border-emerald-400/30 bg-emerald-400/5"
      : status === "fail"
      ? "text-rose-400 border-rose-400/30 bg-rose-400/5"
      : "text-ink-400 border-ink-700 bg-ink-800/50";
  return (
    <div className={`flex items-center justify-between rounded-md px-2.5 py-1.5 border ${color}`}>
      <span className="text-[11.5px]">{label}</span>
      <span className="text-[11px] uppercase tracking-wider">{status}</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border hairline px-3 py-2.5">
      <div className="text-[20px] font-semibold tracking-tight">{value}</div>
      <div className="text-[11.5px] text-ink-500 dark:text-ink-400">{label}</div>
    </div>
  );
}