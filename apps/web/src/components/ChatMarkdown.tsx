"use client";

import type { CSSProperties } from "react";
import ReactMarkdown from "react-markdown";

const mdStyles: Record<string, CSSProperties> = {
  wrapper: {
    fontSize: "0.92rem",
    lineHeight: 1.55,
    color: "#c9d1d9",
  },
  h2: {
    margin: "0.75rem 0 0.4rem",
    fontSize: "1rem",
    fontWeight: 600,
    color: "#e6edf3",
  },
  h3: {
    margin: "0.6rem 0 0.35rem",
    fontSize: "0.95rem",
    fontWeight: 600,
    color: "#e6edf3",
  },
  p: { margin: "0.35rem 0" },
  ul: { margin: "0.35rem 0", paddingLeft: "1.25rem" },
  ol: { margin: "0.35rem 0", paddingLeft: "1.25rem" },
  li: { margin: "0.2rem 0" },
  strong: { color: "#e6edf3", fontWeight: 600 },
  code: {
    fontFamily: "ui-monospace, monospace",
    fontSize: "0.85em",
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: "4px",
    padding: "0.1rem 0.35rem",
  },
  pre: {
    margin: "0.5rem 0",
    padding: "0.65rem",
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: "6px",
    overflowX: "auto",
    fontSize: "0.8rem",
  },
  a: { color: "#58a6ff", textDecoration: "none" },
  hr: { border: "none", borderTop: "1px solid #30363d", margin: "0.75rem 0" },
};

export function ChatMarkdown({ content }: { content: string }) {
  return (
    <div style={mdStyles.wrapper} className="chat-markdown">
      <ReactMarkdown
        components={{
          h2: ({ children }) => <h2 style={mdStyles.h2}>{children}</h2>,
          h3: ({ children }) => <h3 style={mdStyles.h3}>{children}</h3>,
          p: ({ children }) => <p style={mdStyles.p}>{children}</p>,
          ul: ({ children }) => <ul style={mdStyles.ul}>{children}</ul>,
          ol: ({ children }) => <ol style={mdStyles.ol}>{children}</ol>,
          li: ({ children }) => <li style={mdStyles.li}>{children}</li>,
          strong: ({ children }) => <strong style={mdStyles.strong}>{children}</strong>,
          code: ({ children }) => <code style={mdStyles.code}>{children}</code>,
          pre: ({ children }) => <pre style={mdStyles.pre}>{children}</pre>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer" style={mdStyles.a}>
              {children}
            </a>
          ),
          hr: () => <hr style={mdStyles.hr} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
