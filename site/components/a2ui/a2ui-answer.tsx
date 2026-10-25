"use client";

import { A2uiSurface, type ReactCatalogComponent } from "@a2ui/react/v0_9";
import { MessageProcessor } from "@a2ui/web_core/v0_9";
import { useEffect, useState } from "react";

import { networthCatalog } from "@/components/a2ui/catalog";

/** Renders the A2UI messages one server answer carried. */
export function A2uiAnswer({ messages }: { messages: unknown[] }) {
  const [processor] = useState(() => {
    const p = new MessageProcessor<ReactCatalogComponent>([networthCatalog]);
    p.processMessages(messages as Parameters<typeof p.processMessages>[0]);
    return p;
  });
  const [surfaces, setSurfaces] = useState(() => Array.from(processor.model.surfacesMap.values()));
  useEffect(() => {
    const sync = () => setSurfaces(Array.from(processor.model.surfacesMap.values()));
    const created = processor.onSurfaceCreated(sync);
    const deleted = processor.onSurfaceDeleted(sync);
    return () => {
      created.unsubscribe();
      deleted.unsubscribe();
    };
  }, [processor]);
  return <>{surfaces.map((s) => <A2uiSurface key={s.id} surface={s} />)}</>;
}
