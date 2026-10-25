import type { Metadata } from "next";
import { Workspace } from "@/components/workspace";

export const metadata: Metadata = { title: "Sample profile · Networth" };

export default function DemoPage() {
  return <Workspace scope={{ kind: "demo" }} />;
}
