import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    if (next) document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
    try {
      localStorage.setItem("gh-theme", next ? "dark" : "light");
    } catch {}
  }

  return (
    <button
      aria-label="Toggle theme"
      onClick={toggle}
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border hairline bg-white/60 dark:bg-ink-900/60 text-ink-700 dark:text-ink-200 transition hover:bg-white dark:hover:bg-ink-800"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}