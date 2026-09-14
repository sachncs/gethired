import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export function Cta() {
  return (
    <section className="relative py-24 sm:py-32">
      <div className="container-x">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="relative isolate overflow-hidden rounded-3xl border hairline bg-gradient-to-br from-ink-900 to-ink-950 px-8 py-16 text-center text-white sm:px-16 sm:py-24"
        >
          <div
            className="absolute inset-0 -z-10 opacity-60"
            style={{
              background:
                "radial-gradient(60% 60% at 50% 40%, rgba(124,92,255,0.35) 0%, transparent 70%)",
            }}
          />
          <div
            className="absolute inset-0 -z-10 opacity-30"
            style={{
              backgroundImage:
                "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
              backgroundSize: "40px 40px",
              maskImage:
                "radial-gradient(ellipse 80% 60% at 50% 40%, black 30%, transparent 80%)",
            }}
          />
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[12px] font-medium tracking-wide">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-400" />
            MIT · Python 3.12+ · 303 tests
          </span>
          <h2 className="display mx-auto mt-6 max-w-3xl text-[36px] leading-[1.05] sm:text-[60px]">
            Your next resume,
            <br />
            <span className="bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent">
              grounded in everything you've actually done.
            </span>
          </h2>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="https://github.com/sachncs/gethired"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-6 py-3 text-[14.5px] font-semibold tracking-tight text-ink-900 transition hover:-translate-y-[1px] hover:shadow-soft"
            >
              View on GitHub
              <ArrowRight className="h-4 w-4" />
            </a>
            <a
              href="#install"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/20 px-6 py-3 text-[14.5px] font-semibold tracking-tight text-white/90 transition hover:-translate-y-[1px] hover:bg-white/5"
            >
              Install guide
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}