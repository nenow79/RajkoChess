import { Chess } from "chess.js";

export interface ChessMoveOption {
  ply: number;
  label: string;
}

interface MarkdownNode {
  type: string;
  value?: string;
  url?: string;
  children?: MarkdownNode[];
}

export function buildChessMoveOptions(pgn: string | undefined): ChessMoveOption[] {
  if (!pgn) return [];
  try {
    const chess = new Chess();
    chess.loadPgn(pgn);
    return [
      { ply: 0, label: "Pozycja startowa" },
      ...chess.history().map((san, index) => {
        const ply = index + 1;
        const moveNumber = Math.ceil(ply / 2);
        return {
          ply,
          label: ply % 2 ? `${moveNumber}. ${san}` : `${moveNumber}... ${san}`,
        };
      }),
    ];
  } catch {
    return [];
  }
}

const escapePattern = (value: string) => value
  .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  .replace(/\s+/g, "\\s+");

export function remarkChessMoveLinks(options?: { moves?: ChessMoveOption[] }) {
  const playedMoves = (options?.moves || []).filter((move) => move.ply > 0);
  const plyByLabel = new Map(playedMoves.map((move) => [move.label, move.ply]));
  const alternatives = playedMoves
    .map((move) => move.label)
    .sort((left, right) => right.length - left.length)
    .map(escapePattern)
    .join("|");
  const pattern = alternatives
    ? new RegExp(`(^|[^0-9])(${alternatives})(?=$|[^A-Za-z0-9+#=])`, "g")
    : null;

  return (tree: MarkdownNode) => {
    if (!pattern) return;

    const visit = (node: MarkdownNode) => {
      if (!node.children || node.type === "link" || node.type === "code" || node.type === "inlineCode") return;

      for (let index = node.children.length - 1; index >= 0; index -= 1) {
        const child = node.children[index];
        if (child.type !== "text" || typeof child.value !== "string") {
          visit(child);
          continue;
        }

        pattern.lastIndex = 0;
        const replacements: MarkdownNode[] = [];
        let cursor = 0;
        let match: RegExpExecArray | null;
        while ((match = pattern.exec(child.value)) !== null) {
          const prefix = match[1];
          const label = match[2];
          const labelStart = match.index + prefix.length;
          if (labelStart > cursor) {
            replacements.push({ type: "text", value: child.value.slice(cursor, labelStart) });
          }
          const normalizedLabel = label.replace(/\s+/g, " ");
          const ply = plyByLabel.get(normalizedLabel);
          if (ply === undefined) continue;
          replacements.push({
            type: "link",
            url: `#ply-${ply}`,
            children: [{ type: "text", value: label }],
          });
          cursor = labelStart + label.length;
        }
        if (!replacements.length) continue;
        if (cursor < child.value.length) {
          replacements.push({ type: "text", value: child.value.slice(cursor) });
        }
        node.children.splice(index, 1, ...replacements);
      }
    };

    visit(tree);
  };
}
