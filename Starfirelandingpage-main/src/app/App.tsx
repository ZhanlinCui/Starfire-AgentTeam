import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { MarketMomentum } from "./components/MarketMomentum";
import { UseCases } from "./components/UseCases";
import { MemoryArchitecture } from "./components/MemoryArchitecture";
import { Enterprise } from "./components/Enterprise";
import { FinalCTA } from "./components/FinalCTA";
import { Footer } from "./components/Footer";
import { LandingBackground } from "./components/background/LandingBackground";

export default function App() {
  return (
    <div
      className="relative min-h-screen text-gray-100"
      style={{
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        background: "linear-gradient(180deg, #05070f 0%, #0a101d 42%, #111a2b 100%)",
      }}
    >
      <LandingBackground />
      <div className="relative z-10">
        <Header />
        <main>
          <Hero />
          <MarketMomentum />
          <UseCases />
          <MemoryArchitecture />
          <Enterprise />
          <FinalCTA />
        </main>
        <Footer />
      </div>
    </div>
  );
}
