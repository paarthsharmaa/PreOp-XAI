import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { SiteData } from "./types";

const SiteContext = createContext<SiteData | null>(null);

export function SiteProvider({ children }: { children: ReactNode }) {
  const [site, setSite] = useState<SiteData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/site.json`)
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then(setSite)
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <p className="mx-auto max-w-xl px-4 py-24 text-center">
        The results data could not be loaded. Run <code>make app-data</code> and reload this page.
      </p>
    );
  }
  if (!site) return <p className="py-24 text-center text-muted">Loading results…</p>;
  return <SiteContext.Provider value={site}>{children}</SiteContext.Provider>;
}

export function useSite(): SiteData {
  const site = useContext(SiteContext);
  if (!site) throw new Error("Site data is not loaded.");
  return site;
}
