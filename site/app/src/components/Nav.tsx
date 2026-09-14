import { motion } from "framer-motion";
import { Github, Terminal } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

const nav = [
  { href: "#pipeline", label: "Pipeline" },
  { href: "#features", label: "Features" },
  { href: "#gates", label: "ATS Gates" },
  { href: "#cli", label: "CLI" },
  { href: "#faq", label: "FAQ" },
];

export function Nav() {
  return (
    <motion.header
      initial={{ y: -16, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="sticky top-0 z-50 w-full"
    >
      <div className="absolute inset-x-0 top-0 -z-10 h-full bg-gradient-to-b from-ink-50/85 to-ink-50/0 dark:from-ink-950/85 dark:to-ink-950/0 backdrop-blur-xl" />
      <div className="container-x flex h-16 items-center justify-between">
        <a href="#top" className="group inline-flex items-center gap-2.5">
          <span className="grid h-7 w-7 place-items-center rounded-[8px] bg-gradient-to-br from-accent-500 to-accent-700 text-white shadow-glow">
            <span className="font-bold text-[13px] tracking-tight">G</span>
          </span>
          <span className="text-[15px] font-semibold tracking-tight">gethired</span>
          <span className="hidden sm:inline-block rounded-full border hairline px-1.5 py-0.5 text-[10px] font-medium text-ink-500 dark:text-ink-400">
            v0.6
          </span>
        </a>

        <nav className="hidden md:flex items-center gap-1">
          {nav.map((n) => (
            <a
              key={n.href}
              href={n.href}
              className="rounded-full px-3 py-1.5 text-[13.5px] font-medium text-ink-600 dark:text-ink-300 hover:text-ink-900 dark:hover:text-white transition"
            >
              {n.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <a
            href="#install"
            className="btn-primary hidden sm:inline-flex"
          >
            <Terminal className="h-4 w-4" />
            Install
          </a>
          <a
            href="https://github.com/sachncs/gethired"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost"
          >
            <Github className="h-4 w-4" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </div>
    </motion.header>
  );
}