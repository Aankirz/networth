import type { Block, Message } from "@/lib/contract";

function BlockView({ block }: { block: Block }) {
  if (block.kind === "link") {
    return (
      <a href={block.url} rel="noopener">
        {block.label}
      </a>
    );
  }
  return <>{block.text}</>;
}

/** The server's words in full. A card adds structure beside them and never replaces them. */
export function MessageView({ message }: { message: Message }) {
  return (
    <div className="grid gap-2">
      {message.title && <p className="font-medium">{message.title}</p>}
      <p className="max-w-[65ch] whitespace-pre-line">
        {message.body.map((block, i) => (
          <BlockView key={i} block={block} />
        ))}
      </p>
      {message.detail.length > 0 && (
        <details className="group text-graphite">
          <summary className="cursor-pointer text-note text-link">More</summary>
          <div className="mt-2 grid gap-1 whitespace-pre-line">
            {message.detail.map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

export function Footer({ text }: { text: string }) {
  return <p className="text-note italic text-graphite">{text}</p>;
}
