import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useSite } from "../lib/site";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/findings", label: "Findings" },
  { to: "/explorer", label: "Patient explorer" },
  { to: "/methods", label: "Methods" },
  { to: "/team", label: "Team" },
];

export function Layout() {
  const site = useSite();
  const location = useLocation();
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    setMenu(false);
    if (!location.search) window.scrollTo(0, 0);
  }, [location.pathname, location.search]);

  const link = ({ isActive }: { isActive: boolean }) =>
    `block rounded px-3 py-2 text-sm font-medium no-underline transition-colors ${
      isActive ? "bg-accent-soft text-accent-dark" : "text-body hover:bg-wash"
    }`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
          <NavLink to="/" className="font-serif text-xl font-semibold text-ink no-underline">
            PreOp-XAI
          </NavLink>
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === "/"} className={link}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <button
            type="button"
            className="min-h-10 rounded border border-line px-3 text-sm font-medium text-ink md:hidden"
            aria-expanded={menu}
            aria-controls="mobile-nav"
            onClick={() => setMenu(!menu)}
          >
            Menu
          </button>
        </div>
        {menu && (
          <nav id="mobile-nav" aria-label="Mobile" className="border-t border-line px-4 py-2 md:hidden">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === "/"} className={link}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}
        <div role="note" className="border-t border-warn/20 bg-warn-soft">
          <p className="mx-auto max-w-6xl px-4 py-1.5 text-xs font-medium text-warn">{site.notice}</p>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-wash">
        <div className="mx-auto grid max-w-6xl gap-4 px-4 py-8 text-xs leading-relaxed text-muted md:grid-cols-2">
          <p className="m-0">
            <strong className="text-ink">Data: </strong>
            <a href={site.sources.mover.url}>{site.sources.mover.name}</a> (aggregate results only) and{" "}
            <a href={site.sources.vitaldb.url}>{site.sources.vitaldb.name}</a>, Lee HC et al., Sci Data, used under{" "}
            <a href={site.sources.vitaldb.licence_url}>{site.sources.vitaldb.licence}</a>.{" "}
            {site.sources.vitaldb.changes}
          </p>
          <p className="m-0">
            <strong className="text-ink">{site.notice}</strong> These models have not been validated for clinical
            decisions and must not guide patient care.
          </p>
        </div>
      </footer>
    </div>
  );
}
