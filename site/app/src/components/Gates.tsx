import { motion } from "framer-motion";
import { Check, Minus, ShieldAlert } from "lucide-react";

type GateStatus = "pass" | "advisory" | "skip";

const hard: { name: string; desc: string }[] = [
  { name: "pdf_compiles", desc: "PDF compiles without errors" },
  { name: "pdf_text_extract", desc: "Text is extractable from the PDF" },
  { name: "pdf_text_matches", desc: "PDF text matches the .txt source" },
  { name: "headings_standard", desc: "Standard section headings" },
  { name: "no_tables", desc: "No layout tables in the source" },
  { name: "no_images", desc: "No embedded images" },
  { name: "no_colors", desc: "No colour usage" },
  { name: "font_size", desc: "10–12 pt font range" },
  { name: "length_in_page", desc: "Length within page limit" },
];

const advisory: { name: string; desc: string }[] = [
  { name: "keyword_coverage", desc: "Coverage of JD must-haves" },
  { name: "bullet_quant", desc: "Bullets carry quantified outcomes" },
  { name: "action_verbs", desc: "Open with strong action verbs" },
];

function StatusIcon({ status }: { status: GateStatus }) {
  if (status === "pass") return <Check className="h-3.5 w-3.5 text-emerald-500" />;
  if (status === "advisory") return <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />;
  return <Minus className="h-3.5 w-3.5 text-ink-400" />;
}

export function Gates() {
  return (
    <section id="gates" className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-12 lg:gap-14">
          <div className="lg:col-span-5">
            <span className="eyebrow">The ATS contract</span>
            <h2 className="display mt-3 text-[32px] leading-[1.05] sm:text-[44px]">
              12 gates.
              <br />
              <span className="gradient-text">Zero surprises.</span>
            </h2>
            <p className="mt-5 text-[15.5px] sm:text-[17px] text-ink-600 dark:text-ink-300">
              Every tailored run passes through a tri-state gate suite before
              render. A failed hard gate blocks the run — they're the
              reasons real ATS systems reject candidates.
            </p>
            <ul className="mt-7 space-y-3 text-[14.5px] text-ink-700 dark:text-ink-200">
              <li className="flex items-start gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-emerald-500" />
                <span>
                  <span className="font-semibold">9 hard-blocking</span> gates
                  must pass. A failure blocks the render.
                </span>
              </li>
              <li className="flex items-start gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-amber-500" />
                <span>
                  <span className="font-semibold">3 advisory</span> gates
                  report and surface in the match report, but never block.
                </span>
              </li>
              <li className="flex items-start gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-ink-400" />
                <span>
                  PDF gates <span className="font-semibold">skip</span> when
                  <code className="font-mono text-[12.5px] mx-1 rounded bg-ink-100 dark:bg-ink-800 px-1.5 py-0.5">LATEX_ENGINE=none</code>.
                </span>
              </li>
            </ul>
            <div className="mt-8 flex flex-wrap gap-2">
              <span className="chip">Tri-state: pass · fail · skip</span>
              <span className="chip">Re-runnable: <code className="font-mono">tailor audit</code></span>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="surface-strong rounded-2xl p-6 sm:p-8">
                <div className="flex items-center justify-between">
                  <h3 className="text-[14px] font-semibold tracking-tight uppercase">
                    Hard gates
                  </h3>
                  <span className="text-[12px] text-ink-500 dark:text-ink-400 font-mono">
                    blocks run on fail
                  </span>
                </div>
                <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {hard.map((g, i) => (
                    <Gate key={g.name} name={g.name} desc={g.desc} status="pass" index={i} />
                  ))}
                </div>

                <div className="mt-8 flex items-center justify-between">
                  <h3 className="text-[14px] font-semibold tracking-tight uppercase">
                    Advisory gates
                  </h3>
                  <span className="text-[12px] text-ink-500 dark:text-ink-400 font-mono">
                    report only
                  </span>
                </div>
                <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {advisory.map((g, i) => (
                    <Gate
                      key={g.name}
                      name={g.name}
                      desc={g.desc}
                      status="advisory"
                      index={i + hard.length}
                    />
                  ))}
                </div>
              </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Gate({
  name,
  desc,
  status,
  index,
}: {
  name: string;
  desc: string;
  status: GateStatus;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.45, delay: index * 0.03 }}
      className="group flex items-start justify-between gap-3 rounded-xl border hairline bg-white/60 dark:bg-ink-900/60 px-4 py-3"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <StatusIcon status={status} />
          <code className="font-mono text-[13px] font-semibold tracking-tight">{name}</code>
        </div>
        <p className="mt-1 truncate text-[12.5px] text-ink-500 dark:text-ink-400">
          {desc}
        </p>
      </div>
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider ${
          status === "pass"
            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
            : "bg-amber-500/10 text-amber-600 dark:text-amber-300"
        }`}
      >
        {status}
      </span>
    </motion.div>
  );
}