import "@fontsource-variable/inter";
import "@fontsource-variable/source-serif-4";
import "./index.css";

import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { SiteProvider } from "./lib/site";
import { Overview } from "./pages/Overview";
import { Methods } from "./pages/Methods";
import { Team } from "./pages/Team";

const Findings = lazy(() => import("./pages/Findings"));
const Explorer = lazy(() => import("./pages/Explorer"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SiteProvider>
      <HashRouter>
        <Suspense fallback={<p className="py-24 text-center text-muted">Loading…</p>}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Overview />} />
              <Route path="findings" element={<Findings />} />
              <Route path="explorer" element={<Explorer />} />
              <Route path="methods" element={<Methods />} />
              <Route path="team" element={<Team />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </SiteProvider>
  </StrictMode>,
);
