import type { Metadata } from "next";
import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { ArrowRight, Mail, MonitorSmartphone, Send } from "lucide-react";

import { LandingAsk } from "@/components/landing/ask";
import { LiveHistory, LiveNews, LivePlan, LiveRange, LiveTrackRecord } from "@/components/landing/live";
import { Mark } from "@/components/mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { BOT_URL } from "@/lib/chat";

export const metadata: Metadata = {
  title: "Networth · a calm friend for your monthly investing",
  description: "Networth reads the market news, checks it against what happened in the past, and turns up on the day you invest. On Telegram, by email and on the web. Research, not advice.",
};

const STEPS: { title: string; body: string; live: ReactNode }[] = [
  {
    title: "Tell it your plan",
    body: "Send /start to the bot. It asks how much you put in each month, the day you invest and the fall you can sit through.",
    live: <LivePlan />,
  },
  {
    title: "It reads the news for you",
    body: "Each weekday it reads the market news and keeps only what a primary source or several publishers confirm, each with who reported it.",
    live: <LiveNews />,
  },
  {
    title: "On your day, a short brief",
    body: "When you invest, it tells you what happened and what history counted the last times something like it happened.",
    live: <LiveHistory />,
  },
];

const CHANNELS = [
  { icon: Send, name: "Telegram", body: "Your brief, your questions, and a second look at any tip someone forwards you." },
  { icon: Mail, name: "Email", body: "Send /sendto email and the brief comes to your inbox. Reply with a question and the answer comes back by email." },
  { icon: MonitorSmartphone, name: "The web", body: "A private dashboard behind your own link, with the chat one click away. /dashboard in the bot opens it." },
];

const NEVER = [
  "It never tells you what to pick, or when to get in or out.",
  "It never rates a fund or a share, and never gives a tip of its own.",
  "It never talks about trading on borrowed money or in derivatives.",
  "It never colours a count to make it feel like a signal. A count is shown as a count.",
  "It never places an order or moves your money.",
];

const FAQ: { q: string; a: ReactNode }[] = [
  { q: "Is this financial advice?", a: "No. It is research: what the news says and what history counted, in plain words. What you do is your choice." },
  { q: "Do I need an account?", a: <>No. <Link href="/demo">The demo</Link> opens a sample profile. To set up your own, send /start to the bot.</> },
  { q: "What does “what history counted” mean?", a: "For an event like an RBI rate hike, it counts how often an asset beat the Nifty 50 in the past cases, and puts that next to its normal rate. Few cases are called out as too few." },
  { q: "Can it see my money?", a: "Only what you tell it: your plan, and your holdings if you choose to share them. It never places an order." },
  { q: "Which languages does it speak?", a: "English, Hindi and Hinglish. You can change the language for any single answer." },
  { q: "Is my dashboard link private?", a: "Anyone with the link can open it, so keep it to yourself. /erase in the bot deletes everything about you after one confirm tap." },
];

function Section({ id, title, kicker, children }: { id: string; title: string; kicker?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20 border-t border-line py-16 sm:py-20">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 sm:px-6">
        <header className="grid max-w-2xl gap-3">
          {kicker && <p className="text-sm text-ink-3">{kicker}</p>}
          <h2 id={`${id}-title`} className="text-2xl font-semibold tracking-tight sm:text-[2.25rem] sm:leading-tight">{title}</h2>
        </header>
        {children}
      </div>
    </section>
  );
}

function Live({ children, height }: { children: ReactNode; height: string }) {
  return <Suspense fallback={<div className={height} aria-hidden="true" />}>{children}</Suspense>;
}

export default function Landing() {
  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-[color-mix(in_oklch,var(--bg)_88%,transparent)] backdrop-blur">
        <nav aria-label="Main" className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2 text-sm font-semibold no-underline">
            <Mark className="size-5" /> Networth
          </Link>
          <ul className="flex items-center gap-5 text-sm text-ink-2 max-md:hidden">
            <li><a href="#how" className="no-underline hover:text-ink">How it works</a></li>
            <li><a href="#record" className="no-underline hover:text-ink">Track record</a></li>
            <li><a href="#faq" className="no-underline hover:text-ink">FAQ</a></li>
          </ul>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle compact />
            <Link href="/demo" className="btn btn-primary no-underline">Try the demo</Link>
          </div>
        </nav>
      </header>

      <main>
        <section aria-labelledby="hero-title" className="mx-auto grid max-w-6xl gap-10 px-4 pt-16 pb-16 sm:px-6 sm:pt-24 sm:pb-24">
          <h1 id="hero-title" className="max-w-[20ch] text-[2.5rem] leading-[1.05] font-semibold tracking-tight sm:text-[4rem] lg:text-[4.75rem]">
            A calm friend for your monthly investing.
          </h1>
          <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16">
            <div className="grid content-start gap-6">
              <p className="max-w-[48ch] text-lg text-ink-2">
                Networth reads the market news, checks it against what happened in the past, and turns up on the day you invest. On Telegram, by email and on the web.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href="/demo" className="btn btn-primary h-11 px-5 text-base no-underline">
                  Try the demo <ArrowRight aria-hidden="true" />
                </Link>
                <a href={BOT_URL} rel="noopener" target="_blank" className="btn h-11 px-5 text-base no-underline">
                  <Send aria-hidden="true" /> Message the bot
                </a>
              </div>
            </div>
            <LandingAsk />
          </div>
        </section>

        <Section id="how" kicker="How it works" title="Three steps, then it comes to you">
          <ol className="grid gap-16">
            {STEPS.map((step, i) => (
              <li key={step.title} className="grid gap-6 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] md:gap-12">
                <div className="grid content-start gap-3">
                  <p className="figure text-sm text-ink-3">{`0${i + 1}`}</p>
                  <h3 className="text-xl font-semibold">{step.title}</h3>
                  <p className="max-w-[44ch] text-ink-2">{step.body}</p>
                </div>
                <div className="min-w-0 rounded-xl border border-line p-5 sm:p-6">
                  <Live height="min-h-40">{step.live}</Live>
                </div>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="channels" kicker="Where it lives" title="Wherever you already read">
          <ul className="grid gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-3">
            {CHANNELS.map(({ icon: Icon, name, body }) => (
              <li key={name} className="grid content-start gap-3 bg-bg p-6">
                <Icon aria-hidden="true" className="size-5 text-ink-2" />
                <h3 className="font-semibold">{name}</h3>
                <p className="text-ink-2">{body}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="never" kicker="The line we never cross" title="What it will never do">
          <ul className="grid max-w-3xl gap-4">
            {NEVER.map((line) => (
              <li key={line} className="flex gap-3 text-lg">
                <span aria-hidden="true" className="mt-[0.7em] h-px w-4 shrink-0 bg-ink-3" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="record" kicker="Track record" title="We tested ourselves. It came back negative.">
          <div className="grid gap-8 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] md:gap-12">
            <p className="max-w-[44ch] text-ink-2">
              We checked whether a count well above its normal rate said anything about the cases that came next. On years we held back, it did no better than chance. So Networth shows the counts as history, never as a signal.
            </p>
            <Live height="min-h-32">
              <LiveTrackRecord />
            </Live>
          </div>
        </Section>

        <Section id="sample" kicker="Drawn live from the sample profile" title="What a plan could become">
          <div className="grid gap-6">
            <div className="min-w-0 max-w-3xl rounded-xl border border-line p-5 sm:p-6">
              <Live height="min-h-[34rem]">
                <LiveRange />
              </Live>
            </div>
            <p>
              <Link href="/demo" className="inline-flex items-center gap-1.5 underline">
                Ask the sample profile your own question <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </p>
          </div>
        </Section>

        <Section id="faq" kicker="Questions" title="Before you start">
          <div className="grid max-w-3xl divide-y divide-line border-y border-line">
            {FAQ.map(({ q, a }) => (
              <details key={q} name="faq" className="group py-1">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-medium">
                  {q}
                  <span aria-hidden="true" className="figure text-ink-3 transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="max-w-[60ch] pb-5 text-ink-2">{a}</p>
              </details>
            ))}
          </div>
        </Section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-10 text-sm text-ink-3 sm:px-6">
          <span className="flex items-center gap-2 text-ink-2"><Mark className="size-4" /> Networth</span>
          <span>Research, not advice.</span>
          <span className="ml-auto flex gap-5">
            <Link href="/demo" className="no-underline hover:text-ink">Demo</Link>
            <a href={BOT_URL} rel="noopener" target="_blank" className="no-underline hover:text-ink">Telegram bot</a>
          </span>
        </div>
      </footer>
    </>
  );
}
