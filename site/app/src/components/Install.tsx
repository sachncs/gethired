import { motion } from "framer-motion";
import { Copy, Terminal } from "lucide-react";

const snippet = `# Install
git clone https://github.com/sachncs/gethired.git
cd gethired
uv sync
cp .env.example .env
# edit .env: API_KEY=...  MODEL=MiniMax-M3  BASE_URL=https://api.minimax.io/anthropic

# Run
gethired ingest sample.tex
gethired run https://jobs.example.com/senior-platform-engineer

# Output
tailored/<run-id>/
├── tailored.tex        # ATS-compliant LaTeX
├── tailored.txt        # plain-text ATS version
├── tailored.json       # full Tailored with traceability
├── tailored.pdf        # compiled via tectonic
└── match_report.md     # Job Trail · ATS Gates · Coverage`;

export function Install() {
  return (
    <section id="install" className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-12 lg:gap-14">
          <div className="lg:col-span-5">
            <span className="eyebrow">Quick start</span>
            <h2 className="display mt-3 text-[34px] leading-[1.05] sm:text-[46px]">
              From clone to tailored PDF
              <br />
              <span className="gradient-text">in two minutes.</span>
            </h2>
            <p className="mt-5 text-[15.5px] sm:text-[17px] text-ink-600 dark:text-ink-300">
              The CLI loads the full dependency graph at startup; the
              library API defers heavy imports until you need them. Drop in
              a model, point it at a JD, run.
            </p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <a
                href="https://github.com/sachncs/gethired"
                target="_blank"
                rel="noreferrer"
                className="btn-primary px-6 py-3 text-[14.5px]"
              >
                <Terminal className="h-4 w-4" />
                Open repository
              </a>
              <a href="#cli" className="btn-ghost px-6 py-3 text-[14.5px]">
                See all commands
              </a>
            </div>
            <ul className="mt-8 space-y-2 text-[13.5px] text-ink-600 dark:text-ink-300">
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
                Requires Python 3.12 or 3.13.
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
                Works with Anthropic, OpenAI, or any Anthropic-compatible API.
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
                <code className="font-mono text-[12.5px] rounded bg-ink-100 dark:bg-ink-800 px-1.5 py-0.5">MODEL=MiniMax-M3</code> auto-routes.
              </li>
            </ul>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.6 }}
            className="lg:col-span-7"
          >
            <div className="overflow-hidden rounded-2xl border border-ink-800 bg-ink-950 text-ink-100 shadow-soft">
              <div className="flex items-center justify-between border-b border-ink-800 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Terminal className="h-3.5 w-3.5 text-ink-400" />
                  <span className="font-mono text-[12px] text-ink-400">quickstart.sh</span>
                </div>
                <button
                  className="inline-flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-900 px-2.5 py-1 text-[11.5px] text-ink-300 hover:bg-ink-800"
                  onClick={() => {
                    try {
                      navigator.clipboard.writeText(snippet);
                    } catch {}
                  }}
                >
                  <Copy className="h-3 w-3" />
                  Copy
                </button>
              </div>
              <pre className="overflow-x-auto p-6 font-mono text-[12.5px] leading-relaxed">
                <code>{snippet}</code>
              </pre>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}