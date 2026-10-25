import type { Metadata } from "next";
import { Workspace } from "@/components/workspace";

export const metadata: Metadata = { title: "Sample profile · Networth" };

/** `/demo?q=…` arrives from the landing page's composer and is asked straight away. */
export default async function DemoPage({ searchParams }: PageProps<"/demo">) {
  const { q } = await searchParams;
  const ask = typeof q === "string" ? q.trim() : "";
  return <Workspace scope={{ kind: "demo" }} ask={ask || null} />;
}
