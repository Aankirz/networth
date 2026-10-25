import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-4 px-4 py-16">
      <h1 className="text-display">Networth</h1>
      {/* The server's own BAD_LINK words, as on the Maritime /u page. */}
      <p className="max-w-[60ch]">This link has expired or isn&apos;t right. Type /plan in the bot for a fresh one.</p>
      <p>
        <Link href="/demo">See the sample profile instead</Link>
      </p>
    </main>
  );
}
