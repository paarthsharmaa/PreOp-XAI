import { Link } from "react-router-dom";
import { CohortFlow } from "../components/CohortFlow";
import { Stat } from "../components/ui";
import { count } from "../lib/format";
import { useSite } from "../lib/site";

export function Overview() {
  const site = useSite();
  const mover = site.cohort.mover.at(-1)!.n;
  const vitaldb = site.cohort.vitaldb.at(-1)!.n;
  const { mortality } = site.endpoints;

  return (
    <>
      <header className="max-w-3xl pb-10 pt-12 sm:pt-16">
        <p className="font-serif text-2xl font-semibold leading-snug text-accent sm:text-3xl">
          Explainable preoperative risk prediction for mortality and morbidity
        </p>
        <h1 className="mt-4 text-4xl leading-[1.12] sm:text-5xl">Does gradient boosting actually beat logistic regression?</h1>
        <p className="mt-5 text-lg leading-relaxed">
          PreOp-XAI compares logistic regression with XGBoost for predicting in-hospital mortality and ICU admission
          from ten variables available before surgery. It also asks whether their explanations are stable and whether
          they hold up at a different hospital.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/explorer" className="rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white no-underline hover:bg-accent-dark">
            Explore a patient
          </Link>
          <Link to="/findings" className="rounded-md border border-line px-4 py-2.5 text-sm font-medium text-ink no-underline hover:bg-wash">
            Read the findings
          </Link>
        </div>
      </header>

      <section aria-labelledby="answers">
        <h2 id="answers" className="text-2xl">
          Three questions, three answers
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {site.overview.map((card) => (
            <Link
              key={card.question}
              to={`/findings?section=${card.link}`}
              className="group flex flex-col rounded-lg border border-line bg-white p-5 text-body no-underline transition-colors hover:border-accent"
            >
              <span className="text-sm font-medium text-muted">{card.question}</span>
              <span className="mt-2 font-serif text-3xl font-semibold text-ink">{card.answer}</span>
              <span className="mt-3 flex-1 text-sm leading-relaxed">{card.detail}</span>
              <span className="mt-4 text-sm font-medium text-accent group-hover:underline">See the evidence</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-10 grid grid-cols-2 gap-6 border-y border-line py-6 lg:grid-cols-4" aria-label="Study at a glance">
        <Stat label="Development patients" value={count(mover)} note={site.sources.mover.name} />
        <Stat label="External patients" value={count(vitaldb)} note={site.sources.vitaldb.name} />
        <Stat label="Bootstrap resamples" value={count(mortality.test.bootstraps)} note="per endpoint" />
        <Stat label="Repeated splits" value={count(mortality.repeats.splits)} note="per endpoint" />
      </section>

      <section className="mt-10" aria-labelledby="cohort">
        <h2 id="cohort" className="text-2xl">
          How the cohorts were built
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed">
          Hover over or select a step to read it. Bars are drawn to scale against the first step.
        </p>
        <div className="mt-4 rounded-lg border border-line p-4 sm:p-5">
          <CohortFlow />
        </div>
      </section>
    </>
  );
}
