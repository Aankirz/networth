import type { Metadata } from "next";
import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { ArrowRight, Send } from "lucide-react";

import "./landing.css";
import { HeroSketch } from "@/components/landing/hero-sketch";
import { InView } from "@/components/landing/in-view";
import { LiveRange } from "@/components/landing/live";
import { BriefMock, ChatMock, DashboardMock, EmailMock } from "@/components/landing/mocks";
import { StepIcon } from "@/components/landing/step-icons";
import { AccountButton } from "@/components/account/account-button";
import { Mark } from "@/components/mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { BOT_URL } from "@/lib/chat";

export const metadata: Metadata = {
  title: "Networth · market news, checked against history",
  description: "Networth reads the market news, keeps only what's confirmed, and shows what history counted on the day you invest. On Telegram, by email and on the web.",
};

const STEPS = [
  { icon: "plane", title: "Tell it your plan", body: "Send /start to the bot. It asks what you put in each month, the day you invest, and the fall you can sit through." },
  { icon: "news", title: "It reads the news", body: "Each weekday it keeps only the stories a primary source or several publishers confirm, with who reported each one." },
  { icon: "day", title: "On your day, a brief", body: "When you invest, it tells you what happened and what history counted the last times something like it happened." },
] as const;

const NEVER = [
  "It never tells you what to pick, or when to get in or out.",
  "It never rates a fund or a share, and never gives a tip of its own.",
  "It never talks about trading on borrowed money or in derivatives.",
  "It never colours a count to make it look like a signal.",
  "It never places an order or moves your money.",
];

const FAQ: { q: string; a: ReactNode }[] = [
  { q: "Do I need an account?", a: <>No. <Link href="/demo" className="underline">The demo</Link> opens a sample profile. To set up your own, send /start to the bot.</> },
  { q: "What does “what history counted” mean?", a: "For an event like an RBI rate hike, it counts how often an asset beat the Nifty 50 in the past cases, and puts that next to its normal rate. Too few cases are called out as too few." },
  { q: "Can it see my money?", a: "Only what you tell it: your plan, and your holdings if you choose to share them. It never places an order." },
  { q: "Which languages does it speak?", a: "English, Hindi and Hinglish. You can switch for any single answer." },
  { q: "Is my dashboard link private?", a: "Anyone with the link can open it, so keep it to yourself. /erase in the bot deletes everything about you after one confirm tap." },
];

function Live({ children, height }: { children: ReactNode; height: string }) {
  return <Suspense fallback={<div className={height} aria-hidden="true" />}>{children}</Suspense>;
}

/** One big statement, a grey line that finishes it, then the product doing what it says. */
function Feature({ id, title, more, children, className = "py-20 sm:py-28" }: { id: string; title: string; more: string; children: ReactNode; className?: string }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={`scroll-mt-16 px-4 ${className}`}>
      <InView className="mx-auto grid max-w-5xl gap-12 text-center sm:gap-16">
        <header className="rise mx-auto grid max-w-[720px] gap-2">
          <h2 id={`${id}-title`} className="text-[2rem] leading-[1.08] font-semibold tracking-[-0.03em] text-balance sm:text-[3rem]">{title}</h2>
          <p className="text-[1.25rem] leading-snug tracking-[-0.01em] text-balance text-ink-3 sm:text-[1.75rem]">{more}</p>
        </header>
        <div className="rise min-w-0" style={{ ["--i" as string]: 1 }}>{children}</div>
      </InView>
    </section>
  );
}

function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-[color-mix(in_oklch,var(--bg)_86%,transparent)] backdrop-blur-md">
      <nav aria-label="Main" className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4 max-sm:gap-3">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold no-underline">
          {/* A phone keeps the mark alone so Sign in fits beside Try the demo. */}
          <Mark className="size-5" /> <span className="max-sm:sr-only">Networth</span>
        </Link>
        <ul className="mx-auto flex items-center gap-6 text-sm text-ink-2 max-md:hidden">
          <li><a href="#how" className="no-underline hover:text-ink">How it works</a></li>
          <li><a href="#why" className="no-underline hover:text-ink">Why we built it</a></li>
          <li><a href="#faq" className="no-underline hover:text-ink">FAQ</a></li>
        </ul>
        <div className="flex items-center gap-2 max-md:ml-auto">
          <ThemeToggle compact />
          <Link href="/demo" className="btn btn-primary no-underline">Try the demo</Link>
          <AccountButton />
        </div>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <section aria-labelledby="hero-title" className="hero-field overflow-hidden px-4 pt-16 pb-24 text-center sm:pt-24 sm:pb-32">
      <div className="mx-auto grid max-w-[720px] justify-items-center gap-6">
        <p className="rounded-full border border-line bg-raised px-3.5 py-1 text-xs text-ink-2">Built for the Keiki x Maritime hackathon</p>
        <h1 id="hero-title" className="text-[2.6rem] leading-[1.02] font-semibold tracking-[-0.045em] text-balance sm:text-[4.5rem]">
          Market news, checked against history.
        </h1>
        <p className="max-w-[46ch] text-lg text-balance text-ink-2 sm:text-xl">
          Networth reads the news, keeps only what&apos;s confirmed, and shows what history counted on the day you invest.
        </p>
        <div className="mt-2 flex flex-wrap justify-center gap-3">
          <Link href="/demo" className="btn btn-primary h-11 px-5 text-base no-underline">
            Try the demo <ArrowRight aria-hidden="true" />
          </Link>
          <a href={BOT_URL} rel="noopener" target="_blank" className="btn h-11 px-5 text-base no-underline">
            <Send aria-hidden="true" /> Message the bot
          </a>
        </div>
        <p className="text-sm text-ink-3">On Telegram, by email and on the web. No sign-up for the demo.</p>
      </div>
      <div className="mt-16 sm:mt-20">
        <HeroSketch />
      </div>
    </section>
  );
}

function How() {
  return (
    <section id="how" aria-labelledby="how-title" className="scroll-mt-16 border-t border-line px-4 py-24 sm:py-28">
      <div className="mx-auto grid max-w-5xl gap-14 text-center">
        <h2 id="how-title" className="mx-auto max-w-[720px] text-[2rem] leading-[1.08] font-semibold tracking-[-0.03em] text-balance sm:text-[3rem]">
          Three steps. Then it comes to you.
        </h2>
        <InView as="ol" className="grid gap-12 sm:grid-cols-3 sm:gap-8">
          {STEPS.map((step, i) => (
            <li key={step.title} className="rise grid justify-items-center gap-3" style={{ ["--i" as string]: i }}>
              <StepIcon name={step.icon} />
              <h3 className="text-lg font-semibold">{step.title}</h3>
              <p className="max-w-[32ch] text-ink-2">{step.body}</p>
            </li>
          ))}
        </InView>
      </div>
    </section>
  );
}

function Letter() {
  return (
    <section id="why" aria-labelledby="why-title" className="scroll-mt-16 border-t border-line px-4 py-28 sm:py-36">
      <InView className="mx-auto grid max-w-[640px] gap-6 text-[1.0625rem] leading-relaxed text-ink">
        <h2 id="why-title" className="rise text-center text-[2rem] leading-[1.08] font-semibold tracking-[-0.03em] sm:text-[2.5rem]">Why we built this</h2>
        <p className="rise mt-4" style={{ ["--i" as string]: 1 }}>
          Most money news is loud. A headline moves, and it feels like you should do something. We built Networth for the person who puts a fixed amount in every month and wants to stay calm while they do it.
        </p>
        <p className="rise" style={{ ["--i" as string]: 2 }}>
          Each weekday it reads the market news and keeps only the stories that are confirmed. When one of them is the kind of event that has happened before, it counts what happened after the past cases and puts that next to the normal rate.
        </p>
        <p className="rise" style={{ ["--i" as string]: 3 }}>
          We also tested ourselves. We checked whether a count far from its normal rate said anything about the cases that came next. Out of sample, the counts did no better than chance. So we show them as history, never as a signal.
        </p>
        <p className="rise" style={{ ["--i" as string]: 4 }}>
          That is the whole idea. Read the news, see the history, keep your plan.
        </p>
        <p className="rise text-ink-2" style={{ ["--i" as string]: 5 }}>The Networth team</p>
      </InView>
    </section>
  );
}

function Never() {
  return (
    <section id="never" aria-labelledby="never-title" className="scroll-mt-16 border-t border-line px-4 py-24 sm:py-28">
      <InView className="mx-auto grid max-w-[640px] gap-10 text-center">
        <h2 id="never-title" className="rise text-[2rem] leading-[1.08] font-semibold tracking-[-0.03em] sm:text-[2.5rem]">The line we never cross</h2>
        <ul className="grid gap-4 text-lg">
          {NEVER.map((line, i) => (
            <li key={line} className="rise text-balance" style={{ ["--i" as string]: i + 1 }}>{line}</li>
          ))}
        </ul>
      </InView>
    </section>
  );
}

function Faq() {
  return (
    <section id="faq" aria-labelledby="faq-title" className="scroll-mt-16 border-t border-line px-4 py-24 sm:py-32">
      <div className="mx-auto grid max-w-[680px] gap-10">
        <h2 id="faq-title" className="text-center text-[2rem] leading-[1.08] font-semibold tracking-[-0.03em] sm:text-[2.5rem]">Before you start</h2>
        <div className="grid divide-y divide-line border-y border-line">
          {FAQ.map(({ q, a }) => (
            <details key={q} name="faq" className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 font-medium transition-colors hover:text-ink-2">
                {q}
                <span aria-hidden="true" className="figure text-lg text-ink-3 transition-transform duration-200 group-open:rotate-45">+</span>
              </summary>
              <p className="faq-a max-w-[60ch] pb-6 text-ink-2">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line px-4">
      <div className="mx-auto grid max-w-5xl justify-items-center gap-4 py-14 text-center text-sm text-ink-3">
        <span className="flex items-center gap-2 text-ink-2"><Mark className="size-4" /> Networth</span>
        <span className="flex gap-6">
          <Link href="/demo" className="no-underline hover:text-ink">Demo</Link>
          <a href={BOT_URL} rel="noopener" target="_blank" className="no-underline hover:text-ink">Telegram bot</a>
          <Link href="/privacy" className="no-underline hover:text-ink">Privacy</Link>
        </span>
      </div>
    </footer>
  );
}

export default function Landing() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <How />
        <Feature id="chat" title="Ask it anything about money." more="It explains in English, Hindi or Hinglish, and it never picks for you." className="border-t border-line py-24 sm:py-32">
          <ChatMock />
        </Feature>
        <Feature id="brief" title="One short brief, on your day." more="The month's news, your plan, and what history counted.">
          <Live height="min-h-[30rem]">
            <BriefMock />
          </Live>
        </Feature>
        <Feature id="sample" title="History, drawn in pencil." more="The sample profile's plan, replayed over real past months." className="py-20 sm:py-32">
          <div className="mx-auto max-w-3xl rounded-[20px] border border-line p-5 text-left sm:p-8">
            <Live height="min-h-[34rem]">
              <LiveRange />
            </Live>
          </div>
        </Feature>
        <Feature id="email" title="Prefer email? Reply to it." more="Ask a question back and the answer comes by email.">
          <EmailMock />
        </Feature>
        <Feature id="dashboard" title="Your own page, one link away." more="/dashboard in the bot opens everything on one sheet." className="py-24 sm:py-36">
          <Live height="min-h-[28rem]">
            <DashboardMock />
          </Live>
          <p className="mt-10">
            <Link href="/demo" className="btn btn-primary h-11 px-5 text-base no-underline">
              Open the sample profile <ArrowRight aria-hidden="true" />
            </Link>
          </p>
        </Feature>
        <Letter />
        <Never />
        <Faq />
      </main>
      <Footer />
    </>
  );
}
