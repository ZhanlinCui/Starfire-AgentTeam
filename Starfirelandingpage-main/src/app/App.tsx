import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { MarketMomentum } from "./components/MarketMomentum";
import { UseCases } from "./components/UseCases";
import { MemoryArchitecture } from "./components/MemoryArchitecture";
import { Enterprise } from "./components/Enterprise";
import { FinalCTA } from "./components/FinalCTA";
import { Footer } from "./components/Footer";
import { LandingBackground } from "./components/background/LandingBackground";
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY, type Locale } from "./i18n";

export default function App() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (saved === "en" || saved === "zh") {
      setLocale(saved);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale]);

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
        <Header locale={locale} onLocaleChange={setLocale} />
        <main>
          <Hero locale={locale} />
          <MarketMomentum locale={locale} />
          <UseCases locale={locale} />
          <MemoryArchitecture locale={locale} />
          <Enterprise locale={locale} />
          <FinalCTA locale={locale} />
        </main>
        <Footer locale={locale} />
      </div>
    </div>
  );
}
