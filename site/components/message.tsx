import type { Block, Message } from "@/lib/contract";

function BlockView({ block }: { block: Block }) {
  if (block.kind === "link") {
    return (
      <a href={block.url} rel="noopener" className="underline">
        {block.label}
      </a>
    );
  }
  return <>{block.text}</>;
}

/** The server's words in full. A card adds structure beside them and never replaces them. */
export function MessageView({ message, showTitle = true }: { message: Message; showTitle?: boolean }) {
  const body = message.body.filter((b) => b.kind === "link" || b.text.trim());
  return (
    <div className="grid gap-2">
      {showTitle && message.title && <p className="font-medium">{message.title}</p>}
      {body.length > 0 && (
        <p className="max-w-[68ch] whitespace-pre-line text-ink">
          {body.map((block, i) => (
            <BlockView key={i} block={block} />
          ))}
        </p>
      )}
    </div>
  );
}

export function Footer({ text }: { text: string }) {
  return text ? <p className="text-xs text-ink-3">{text}</p> : null;
}
