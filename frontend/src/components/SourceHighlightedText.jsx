import { useMemo, useState } from "react";

export default function SourceHighlightedText({ text, sourceMap }) {
  const [tooltip, setTooltip] = useState(null);

  const parts = useMemo(() => {
    const output = [];
    let remaining = text || "";
    const entries = Object.entries(sourceMap || {});

    entries.forEach(([claim, source]) => {
      const index = remaining.indexOf(claim);
      if (index !== -1) {
        if (index > 0) {
          output.push({ type: "text", value: remaining.slice(0, index) });
        }
        output.push({ type: "claim", value: claim, source });
        remaining = remaining.slice(index + claim.length);
      }
    });

    if (remaining) {
      output.push({ type: "text", value: remaining });
    }

    return output;
  }, [text, sourceMap]);

  return (
    <>
      <div>
        {parts.map((part, idx) =>
          part.type === "claim" ? (
            <span
              key={idx}
              className="underline decoration-dotted decoration-blue-400 cursor-help"
              onMouseEnter={(event) =>
                setTooltip({
                  claim: part.value,
                  source: part.source,
                  x: event.clientX,
                  y: event.clientY,
                })
              }
              onMouseLeave={() => setTooltip(null)}
            >
              {part.value}
            </span>
          ) : (
            <span key={idx}>{part.value}</span>
          )
        )}
      </div>

      {tooltip && (
        <div
          className="fixed z-50 bg-slate-900 border border-blue-500 rounded-lg p-3 max-w-sm shadow-xl"
          style={{ left: tooltip.x + 10, top: tooltip.y + 10 }}
        >
          <div className="text-xs text-blue-400 mb-1">Source:</div>
          <a
            href={tooltip.source}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-white hover:text-blue-300 break-all"
          >
            {tooltip.source}
          </a>
        </div>
      )}
    </>
  );
}
