import { PageHeader } from "../components/ui";
import { useSite } from "../lib/site";

const MEMBERS = ["Paarth Sharma", "Manas Lahora", "Yug Sharma"];

export function Team() {
  const { sources } = useSite();
  return (
    <>
      <PageHeader eyebrow="Team" title="The people and data behind PreOp-XAI">
        A B.Tech minor project in Artificial Intelligence and Data Science at VIPS.
      </PageHeader>

      <section aria-labelledby="group">
        <h2 id="group" className="text-2xl">Project group</h2>
        <ul className="m-0 mt-4 grid list-none gap-3 p-0 sm:grid-cols-3">
          {MEMBERS.map((name) => (
            <li key={name} className="rounded-lg border border-line p-4 font-serif text-lg font-semibold text-ink">{name}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="supervisor" className="mt-8">
        <h2 id="supervisor" className="text-2xl">Supervisor</h2>
        <p className="mt-3 font-serif text-lg font-semibold text-ink">Ms Anjani Gupta</p>
      </section>

      <section aria-labelledby="sources" className="mt-8">
        <h2 id="sources" className="text-2xl">Data sources</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <article className="rounded-lg border border-line p-4">
            <h3 className="text-lg"><a href={sources.mover.url}>{sources.mover.name}</a></h3>
            <p className="m-0 mt-2 text-sm leading-relaxed">{sources.mover.detail}</p>
          </article>
          <article className="rounded-lg border border-line p-4">
            <h3 className="text-lg"><a href={sources.vitaldb.url}>{sources.vitaldb.name}</a></h3>
            <p className="m-0 mt-2 text-sm leading-relaxed">{sources.vitaldb.detail}</p>
            <p className="m-0 mt-2 text-sm leading-relaxed">
              Licensed under <a href={sources.vitaldb.licence_url}>{sources.vitaldb.licence}</a>. {sources.vitaldb.changes}
            </p>
          </article>
        </div>
      </section>
    </>
  );
}
