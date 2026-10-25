"use client";

import { createComponentImplementation, type ReactCatalogComponent } from "@a2ui/react/v0_9";
import { Catalog, CommonSchemas } from "@a2ui/web_core/v0_9";
import { useId } from "react";
import { z } from "zod";

import { SipProjection } from "@/components/a2ui/sip-projection";
import { money } from "@/lib/money";

// Networth's A2UI catalog. The Python server is the only author of a surface: it sends
// createSurface / updateComponents / updateDataModel messages naming these components, and the
// sliders write back into the surface's own data model, so the projection reruns in the browser
// with no model and no network call.

export const NETWORTH_CATALOG_ID = "https://networth-eight-pied.vercel.app/a2ui/catalog/v1";

const ColumnApi = {
  name: "Column",
  schema: z.object({ children: CommonSchemas.ChildList }),
};
const Column = createComponentImplementation(ColumnApi, ({ props, buildChild }) => {
  const children = Array.isArray(props.children) ? props.children : [];
  return <div className="grid gap-5">{children.map((id) => <div key={String(id)}>{buildChild(String(id))}</div>)}</div>;
});

const TextApi = {
  name: "Text",
  schema: z.object({ text: CommonSchemas.DynamicString, variant: z.enum(["asked", "lead", "body"]).default("body") }),
};
const TEXT = { asked: "text-sm text-ink-3", lead: "text-lg font-semibold text-ink", body: "text-ink-2" };
const Text = createComponentImplementation(TextApi, ({ props }) => (
  <p className={TEXT[props.variant]}>{props.text}</p>
));

const SliderApi = {
  name: "Slider",
  schema: z.object({
    label: CommonSchemas.DynamicString,
    value: CommonSchemas.DynamicNumber,
    min: z.number(),
    max: z.number(),
    step: z.number(),
    unit: z.enum(["money", "percent", "years"]),
    currency: CommonSchemas.DynamicString.optional(),
  }),
};
const SHOW = {
  money: (n: number, currency: string) => money(n, currency),
  percent: (n: number) => `${n}%`,
  years: (n: number) => `${n} yrs`,
};
const Slider = createComponentImplementation(SliderApi, ({ props }) => {
  const id = useId();
  const value = Number(props.value ?? props.min);
  return (
    <div className="grid gap-1.5">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <label htmlFor={id} className="text-ink-2">{props.label}</label>
        <output htmlFor={id} className="figure font-medium text-ink">{SHOW[props.unit](value, props.currency ?? "")}</output>
      </div>
      <input
        id={id}
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={value}
        onChange={(e) => props.setValue(Number(e.target.value))}
        className="h-6 w-full cursor-pointer accent-[var(--accent-stroke)]"
      />
    </div>
  );
});

const SipApi = {
  name: "SipProjection",
  schema: z.object({
    monthly: CommonSchemas.DynamicNumber,
    returnPct: CommonSchemas.DynamicNumber,
    years: CommonSchemas.DynamicNumber,
    stepUpPct: CommonSchemas.DynamicNumber,
    currency: CommonSchemas.DynamicString,
  }),
};
const Sip = createComponentImplementation(SipApi, ({ props }) => (
  <SipProjection
    monthly={Number(props.monthly)}
    returnPct={Number(props.returnPct)}
    years={Math.round(Number(props.years))}
    stepUpPct={Number(props.stepUpPct)}
    currency={String(props.currency)}
  />
));

export const networthCatalog = new Catalog<ReactCatalogComponent>(NETWORTH_CATALOG_ID, "v0.9", [Column, Text, Slider, Sip], []);
