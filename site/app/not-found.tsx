import { Mark } from "@/components/mark";

export default function NotFound() {
  return (
    <main className="mx-auto grid min-h-dvh max-w-xl content-center gap-5 px-4">
      <Mark className="size-8 text-ink-2" />
      <h1 className="text-2xl font-semibold tracking-tight">This link isn&apos;t working</h1>
      {/* The server's own BAD_LINK words, as on the Maritime /u page. */}
      <p className="max-w-[60ch] text-ink-2">This link has expired or isn&apos;t right. Type /plan in the bot for a fresh one.</p>
      <p className="flex flex-wrap gap-2">
        <a href="/demo" className="btn btn-primary">Try the sample profile</a>
        <a href="https://t.me/networth_professor_bot" className="btn" rel="noopener">Message the bot</a>
      </p>
    </main>
  );
}
