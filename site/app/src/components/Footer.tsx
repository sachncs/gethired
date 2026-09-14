import { Github } from "lucide-react";

const cols = [
  {
    title: "Product",
    links: [
      { href: "#pipeline", label: "Pipeline" },
      { href: "#features", label: "Features" },
      { href: "#gates", label: "ATS gates" },
      { href: "#cli", label: "CLI" },
      { href: "#install", label: "Install" },
    ],
  },
  {
    title: "Resources",
    links: [
      { href: "https://github.com/sachncs/gethired", label: "Repository" },
      { href: "https://github.com/sachncs/gethired/blob/main/README.md", label: "Documentation" },
      { href: "https://github.com/sachncs/gethired/blob/main/CHANGELOG.md", label: "Changelog" },
      { href: "https://github.com/sachncs/gethired/blob/main/CONTRIBUTING.md", label: "Contributing" },
      { href: "https://github.com/sachncs/gethired/blob/main/SECURITY.md", label: "Security" },
    ],
  },
  {
    title: "Project",
    links: [
      { href: "https://github.com/sachncs/gethired/blob/main/LICENSE", label: "MIT License" },
      { href: "https://github.com/sachncs/gethired/blob/main/CODE_OF_CONDUCT.md", label: "Code of Conduct" },
      { href: "https://github.com/sachncs/gethired/blob/main/SUPPORT.md", label: "Support" },
      { href: "https://github.com/sachncs/gethired/issues", label: "Issues" },
      { href: "https://github.com/sachncs/gethired/releases", label: "Releases" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative border-t hairline">
      <div className="container-x py-16">
        <div className="grid grid-cols-2 gap-10 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <div className="flex items-center gap-2.5">
              <span className="grid h-7 w-7 place-items-center rounded-[8px] bg-gradient-to-br from-accent-500 to-accent-700 text-white">
                <span className="font-bold text-[13px]">G</span>
              </span>
              <span className="text-[15px] font-semibold tracking-tight">gethired</span>
            </div>
            <p className="mt-4 max-w-xs text-[13.5px] text-ink-600 dark:text-ink-300">
              A multi-agent CV tailoring system grounded in a master resume
              and verified against 12 ATS gates.
            </p>
            <a
              href="https://github.com/sachncs/gethired"
              target="_blank"
              rel="noreferrer"
              className="mt-5 inline-flex items-center gap-2 text-[13.5px] font-medium text-ink-700 dark:text-ink-200 hover:text-accent-500"
            >
              <Github className="h-4 w-4" />
              sachncs/gethired
            </a>
          </div>

          {cols.map((c) => (
            <div key={c.title}>
              <div className="text-[12px] font-semibold uppercase tracking-[0.18em] text-ink-500 dark:text-ink-400">
                {c.title}
              </div>
              <ul className="mt-4 space-y-2.5">
                {c.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      target={l.href.startsWith("http") ? "_blank" : undefined}
                      rel={l.href.startsWith("http") ? "noreferrer" : undefined}
                      className="text-[13.5px] text-ink-700 dark:text-ink-200 hover:text-accent-500"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-start justify-between gap-3 border-t hairline pt-6 text-[12.5px] text-ink-500 dark:text-ink-400 sm:flex-row sm:items-center">
          <div>© 2026 Maintainer · Released under the MIT License.</div>
          <div className="flex items-center gap-3">
            <span>v0.6.0</span>
            <span className="h-1 w-1 rounded-full bg-ink-300 dark:bg-ink-700" />
            <a
              href="https://github.com/sachncs/gethired/actions"
              target="_blank"
              rel="noreferrer"
              className="hover:text-ink-700 dark:hover:text-ink-200"
            >
              CI passing
            </a>
            <span className="h-1 w-1 rounded-full bg-ink-300 dark:bg-ink-700" />
            <a
              href="https://github.com/sachncs/gethired/releases"
              target="_blank"
              rel="noreferrer"
              className="hover:text-ink-700 dark:hover:text-ink-200"
            >
              Latest release
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}