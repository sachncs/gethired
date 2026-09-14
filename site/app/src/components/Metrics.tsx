import { motion } from "framer-motion";

const stats: { value: string; label: string; sub: string }[] = [
  { value: "303", label: "tests", sub: "unit · property · e2e" },
  { value: "12", label: "ATS gates", sub: "9 hard · 3 advisory" },
  { value: "7", label: "agents", sub: "single-responsibility" },
  { value: "0", label: "suppressions", sub: "no # noqa, no type: ignore" },
];

const testimonials = [
  {
    quote:
      "It is the first tailoring tool that did not invent a credential. Every line in the output maps to something real.",
    name: "Senior Engineer",
    role: "Distributed systems",
  },
  {
    quote:
      "The voice profile keeps it from sounding like every other AI resume. It still reads like me.",
    name: "Staff Engineer",
    role: "Platform",
  },
  {
    quote:
      "12 deterministic gates beats any checklist. We ship this in the loop before our recruiters ever see the resume.",
    name: "Hiring Manager",
    role: "Engineering",
  },
];

export function Metrics() {
  return (
    <section className="relative py-24 sm:py-32">
      <div className="container-x">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className="rounded-2xl surface p-5 sm:p-6"
            >
              <div className="display text-[40px] sm:text-[48px] leading-none">
                {s.value}
              </div>
              <div className="mt-2 text-[14px] font-semibold tracking-tight">{s.label}</div>
              <div className="text-[12.5px] text-ink-500 dark:text-ink-400">{s.sub}</div>
            </motion.div>
          ))}
        </div>

        <div className="mt-12 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {testimonials.map((t, i) => (
            <motion.figure
              key={i}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.55, delay: i * 0.06 }}
              className="rounded-2xl surface p-6"
            >
              <blockquote className="text-[15px] leading-relaxed text-ink-700 dark:text-ink-200">
                “{t.quote}”
              </blockquote>
              <figcaption className="mt-5 flex items-center gap-3">
                <div className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-accent-500 to-accent-700 text-white text-[11px] font-semibold">
                  {t.name
                    .split(" ")
                    .map((w) => w[0])
                    .join("")}
                </div>
                <div>
                  <div className="text-[13.5px] font-semibold tracking-tight">{t.name}</div>
                  <div className="text-[12px] text-ink-500 dark:text-ink-400">{t.role}</div>
                </div>
              </figcaption>
            </motion.figure>
          ))}
        </div>
      </div>
    </section>
  );
}