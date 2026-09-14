import { motion } from "framer-motion";
import { useState } from "react";

type Tab = "input" | "tailored" | "report";

const input = `// Master resume (excerpt, .tex → Master)
Master
  name: "A. Patel"
  email: "a.patel@example.com"
  summary: "Backend engineer with 7+ years building
            distributed systems on Kubernetes and Postgres."
  experience[0]
    role: "Senior Software Engineer"
    company: "Northwind"
    bullets:
      - "Owned the payments service: 99.95% uptime, p99 220ms."
      - "Led migration of 14 monoliths to gRPC; -38% latency."`;

const tailored = `// Tailored for Senior Platform Engineer @ Acme
Tailored
  rationale: "Reframed payments ownership around reliability +
              platform leverage. Quantified outcomes preserved verbatim."
  experience[0].bullets:
    - "Owned the payments platform on Kubernetes:
       99.95% uptime, p99 220ms."
    - "Led migration of 14 services to gRPC;
       -38% p99 latency, broader platform reach."`;

const report = `match_report.md · run-7f3a
──────────────────────────────
Role:        Senior Platform Engineer
Company:     Acme
Coverage:    92%   (must-haves 11/12)
Citations:   6     (grounded in master)
Voice drift: 0.04  (threshold 0.12)

ATS Gates · 12/12 PASS
  ✓ pdf_compiles
  ✓ pdf_text_extract
  ✓ pdf_text_matches
  ✓ headings_standard
  ✓ no_tables · no_images · no_colors
  ✓ font_size · length_in_page
  ◐ keyword_coverage · bullet_quant · action_verbs`;

export function Showcase() {
  const [tab, setTab] = useState<Tab>("input");

  return (
    <section className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">See it in motion</span>
          <h2 className="display mt-3 text-[34px] leading-[1.05] sm:text-[48px]">
            From master to tailored,
            <br />
            <span className="gradient-text">without the lies.</span>
          </h2>
          <p className="mt-5 text-[16px] sm:text-[17px] text-ink-600 dark:text-ink-300">
            The same candidate, the same achievements — rewritten to speak
            to the role, with every change traceable to a span in the
            master.
          </p>
        </div>

        <div className="mt-12 overflow-hidden rounded-2xl border hairline bg-ink-50 dark:bg-ink-950">
          <div className="flex items-center justify-between border-b hairline bg-white/60 dark:bg-ink-900/60 px-3 py-2">
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-ink-300 dark:bg-ink-700" />
              <span className="h-2.5 w-2.5 rounded-full bg-ink-300 dark:bg-ink-700" />
              <span className="h-2.5 w-2.5 rounded-full bg-ink-300 dark:bg-ink-700" />
            </div>
            <div className="flex items-center gap-1 rounded-full bg-ink-100/70 dark:bg-ink-800/70 p-1">
              <TabButton active={tab === "input"} onClick={() => setTab("input")}>
                Master
              </TabButton>
              <TabButton active={tab === "tailored"} onClick={() => setTab("tailored")}>
                Tailored
              </TabButton>
              <TabButton active={tab === "report"} onClick={() => setTab("report")}>
                Match report
              </TabButton>
            </div>
            <div className="hidden sm:block text-[12px] text-ink-500 dark:text-ink-400 font-mono">
              {tab === "report" ? "audit.json" : tab === "tailored" ? "tailored.json" : "data/resume.json"}
            </div>
          </div>

          <motion.pre
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="overflow-x-auto p-6 sm:p-8 font-mono text-[12.5px] sm:text-[13px] leading-relaxed text-ink-800 dark:text-ink-100"
          >
            <code>{tab === "input" ? input : tab === "tailored" ? tailored : report}</code>
          </motion.pre>
        </div>
      </div>
    </section>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-[12.5px] font-medium transition ${
        active
          ? "bg-white dark:bg-ink-900 text-ink-900 dark:text-white shadow-soft"
          : "text-ink-500 dark:text-ink-400 hover:text-ink-800 dark:hover:text-ink-100"
      }`}
    >
      {children}
    </button>
  );
}