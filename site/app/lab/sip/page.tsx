import type { Metadata } from "next";

import { AnswerSurface } from "@/components/a2ui/answer-surface";
import { PageFrame } from "@/components/account/page-frame";
import messages from "@/e2e/fixtures/a2ui-sip.json";

// The A2UI spike: the messages a Networth answer carries for an SIP question, rendered by the
// Networth catalog. Phase 13A's server emits this shape; until then it is a fixture.
export const metadata: Metadata = { title: "SIP projection · Networth lab", robots: { index: false } };

export default function SipLab() {
  return (
    <PageFrame>
      <section className="rounded-2xl border border-line bg-raised p-5 sm:p-6">
        <AnswerSurface messages={messages} />
      </section>
    </PageFrame>
  );
}
