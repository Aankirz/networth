import type { Metadata } from "next";
import Link from "next/link";

import { PageFrame } from "@/components/account/page-frame";

export const metadata: Metadata = {
  title: "Privacy · Networth",
  description: "What Networth keeps when you sign in with Google, what it never keeps, and how to erase it.",
};

const KEEP = [
  "Your Google account's subject id, a number Google gives each account. It is how we know it's you.",
  "Your display name from Google, to greet you.",
  "The link between that Google account and your Telegram profile, made with a /weblink code.",
];

const NEVER = [
  "Google's sign-in tokens past your session. They are dropped as soon as you're signed in.",
  "Your email address, your contacts or your mail.",
  "Your Google picture. The avatar is the first letter of your name.",
];

export default function PrivacyPage() {
  return (
    <PageFrame>
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.03em]">Privacy</h1>
      <p className="text-lg text-ink-2">Signing in with Google is only a way to open your own page. Here is everything that involves.</p>
      <section aria-labelledby="keep" className="grid gap-3">
        <h2 id="keep" className="text-xl font-semibold">What we keep</h2>
        <ul className="grid list-disc gap-2 pl-5 text-ink">
          {KEEP.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </section>
      <section aria-labelledby="never" className="grid gap-3">
        <h2 id="never" className="text-xl font-semibold">What we never keep</h2>
        <ul className="grid list-disc gap-2 pl-5 text-ink">
          {NEVER.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </section>
      <section aria-labelledby="erase" className="grid gap-3">
        <h2 id="erase" className="text-xl font-semibold">How to erase it</h2>
        <p className="text-ink">
          On the site, open your account menu and choose &ldquo;Forget me on the web&rdquo;. That removes the Google link and signs you out; your Telegram profile stays. To delete everything Networth has about you, send /erase to the bot. That also removes the Google link.
        </p>
      </section>
      <p className="text-sm text-ink-3">
        Your plan and chat stay on the server you already use with the bot. The <Link href="/demo" className="underline">demo</Link> keeps nothing about you.
      </p>
    </PageFrame>
  );
}
