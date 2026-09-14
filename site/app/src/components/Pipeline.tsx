import { motion } from "framer-motion";

const agents = [
  { name: "Parser", desc: "text · pdf · image · tex → Master", tone: "bg-accent-500/10 text-accent-700 dark:text-accent-200" },
  { name: "Fetcher", desc: "URL → Job · httpx · retry · cache", tone: "bg-sky-500/10 text-sky-700 dark:text-sky-200" },
  { name: "Description", desc: "role · seniority · must-haves", tone: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-200" },
  { name: "Profiler", desc: "voice fingerprint from master", tone: "bg-amber-500/10 text-amber-700 dark:text-amber-200" },
  { name: "Writer", desc: "Pydantic AI · 7 read-only tools", tone: "bg-rose-500/10 text-rose-700 dark:text-rose-200" },
  { name: "Critic", desc: "grounding · style · plagiarism · ATS", tone: "bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-200" },
  { name: "Renderer", desc: "Tailored → tex · txt · pdf · report", tone: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-200" },
];

export function Pipeline() {
  return (
    <section id="pipeline" className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">Multi-agent architecture</span>
          <h2 className="display mt-3 text-[34px] leading-[1.05] sm:text-[48px]">
            Seven small collaborators.
            <br />
            <span className="gradient-text">One tailored resume.</span>
          </h2>
          <p className="mt-5 text-[16px] sm:text-[17px] text-ink-600 dark:text-ink-300">
            Each agent is a small class with one responsibility and a typed
            dependency contract. The <code className="font-mono text-[13.5px] rounded bg-ink-100 dark:bg-ink-800 px-1.5 py-0.5">Tailor</code> class
            is the only collaborator that holds all the others.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a, i) => (
            <motion.div
              key={a.name}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
              className="relative rounded-2xl surface p-5"
            >
              <div className="flex items-center gap-3">
                <div className={`grid h-9 w-9 place-items-center rounded-xl text-[12px] font-bold ${a.tone}`}>
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div>
                  <div className="text-[15px] font-semibold tracking-tight">{a.name}</div>
                  <div className="text-[12.5px] text-ink-500 dark:text-ink-400 font-mono">
                    {a.desc}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="mt-10 surface rounded-2xl p-6 sm:p-8">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <FlowPoint
              k="parse"
              v="Master"
              note="Structured representation of the candidate, including verbatim spans for grounding."
            />
            <FlowPoint
              k="fetch + describe"
              v="Job"
              note="JD parsed into role, seniority, must-haves and nice-to-haves. Multi-URL runs merge via an LLM."
            />
            <FlowPoint
              k="profile + write + critique"
              v="Tailored"
              note="Voice-preserving rewrite, then critic runs grounding, style, plagiarism and the 12 ATS gates."
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function FlowPoint({ k, v, note }: { k: string; v: string; note: string }) {
  return (
    <div>
      <div className="font-mono text-[12px] uppercase tracking-wider text-ink-500 dark:text-ink-400">
        {k}
      </div>
      <div className="mt-1 text-[20px] font-semibold tracking-tight">{v}</div>
      <p className="mt-2 text-[13.5px] text-ink-600 dark:text-ink-300">{note}</p>
    </div>
  );
}