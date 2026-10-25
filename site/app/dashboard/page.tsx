import type { Metadata } from "next";
import Link from "next/link";

import { signInWithGoogle } from "@/app/account-actions";
import { LinkForm } from "@/components/account/link-form";
import { PageFrame } from "@/components/account/page-frame";
import { Workspace } from "@/components/workspace";
import { getAccount } from "@/lib/api";
import { BOT_URL } from "@/lib/chat";
import { signedIn } from "@/lib/session";

export const metadata: Metadata = { title: "Your dashboard · Networth", referrer: "no-referrer" };

function SignIn({ note }: { note?: string }) {
  return (
    <PageFrame>
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.03em]">See your own plan</h1>
      <p className="text-lg text-ink-2">Sign in with Google, then link the account you use with the Telegram bot. Your plan, your brief and your chat follow you here.</p>
      {note && <p role="alert" className="text-ink">{note}</p>}
      <form action={signInWithGoogle}>
        <button type="submit" className="btn btn-primary h-11 px-5 text-base">Sign in with Google</button>
      </form>
      <p className="text-sm text-ink-3">
        Just looking? <Link href="/demo" className="underline">The demo</Link> needs no sign-in.
      </p>
    </PageFrame>
  );
}

function LinkStep({ name, note }: { name: string; note?: string }) {
  return (
    <PageFrame>
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.03em]">{name ? `Hi ${name}. One step to go.` : "One step to go."}</h1>
      <p className="text-lg text-ink">
        Send /weblink to{" "}
        <a href={BOT_URL} rel="noopener" target="_blank" className="underline">@networth_professor_bot</a>{" "}
        and type the code here.
      </p>
      {note && <p role="alert" className="text-ink">{note}</p>}
      <LinkForm />
      <p className="text-sm text-ink-3">A code works once, for 10 minutes. New to Networth? Send /start to the bot to set up your plan first.</p>
    </PageFrame>
  );
}

function Unavailable() {
  return (
    <PageFrame>
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.03em]">Networth is waking up</h1>
      <p className="text-ink-2">Your page can&apos;t load right now. Try again in a minute.</p>
    </PageFrame>
  );
}

const NOTES: Record<string, string> = {
  failed: "Networth couldn't forget the link just now. Try again in a minute.",
};

export default async function DashboardPage({ searchParams }: PageProps<"/dashboard">) {
  const params = await searchParams;
  const visitor = await signedIn();
  if (!visitor) return <SignIn note={params.error ? "Google sign-in didn't finish. Try again." : undefined} />;
  const account = await getAccount(visitor);
  if (!account.ok) return account.status === 401 ? <SignIn note="Your sign-in has run out. Sign in again to go on." /> : <Unavailable />;
  const forget = typeof params.forget === "string" ? NOTES[params.forget] : undefined;
  if (!account.data.linked) return <LinkStep name={visitor.name} note={forget} />;
  return <Workspace scope={{ kind: "me", visitor }} />;
}
