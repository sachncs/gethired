import { Nav } from "./components/Nav";
import { Hero } from "./components/Hero";
import { TrustStrip } from "./components/TrustStrip";
import { Pillars } from "./components/Pillars";
import { Pipeline } from "./components/Pipeline";
import { Gates } from "./components/Gates";
import { Cli } from "./components/Cli";
import { Showcase } from "./components/Showcase";
import { Metrics } from "./components/Metrics";
import { Install } from "./components/Install";
import { Faq } from "./components/Faq";
import { Cta } from "./components/Cta";
import { Footer } from "./components/Footer";

export default function App() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main>
        <Hero />
        <TrustStrip />
        <Pillars />
        <Pipeline />
        <Gates />
        <Showcase />
        <Cli />
        <Metrics />
        <Install />
        <Faq />
        <Cta />
      </main>
      <Footer />
    </div>
  );
}