export type AppMode = "analysis" | "game";
export type PlayerColor = "white" | "black";
export type PlayerColorChoice = PlayerColor | "random";

export interface RatingRange {
  min: number;
  max: number;
}

export interface GameNavigation {
  currentPly: number;
  totalPlies: number;
  moveLabel: string;
}

export interface EvaluationPoint {
  ply: number;
  move_number: number;
  move_label: string;
  evaluation: number;
}

export interface GameAnalysis {
  evaluation_series: EvaluationPoint[];
}

export interface ChessComGame {
  id: string;
  pgn: string;
  color: PlayerColor;
  opponent: string;
  result: string;
  time_class: string;
  rating: number;
  opponent_rating: number;
  played_at: string | null;
  move_count: number | null;
  [key: string]: unknown;
}

export interface ImportedGame {
  pgn: string;
  id?: string;
  color?: PlayerColor;
  opponent?: string;
  result?: string | null;
  bot?: BotProfile;
  [key: string]: unknown;
}

export interface ExplorerMove {
  uci: string;
  san: string;
  play_rate_pct: number;
  white_win_pct: number;
  draw_pct: number;
  black_win_pct: number;
}

export interface ExplorerData {
  opening_eco: string | null;
  opening_name: string | null;
  opening_is_fallback: boolean;
  total_games_analyzed: number;
  top_moves: ExplorerMove[];
}

export interface EngineVariation {
  evaluation: number | string;
  depth: number;
  line_san: string[];
}

export interface PositionAnalysis {
  variations: EngineVariation[];
}

export type BotStyleKey = "aggression" | "tacticality" | "risk" | "materialism" | "simplification";
export type BotStyle = Record<BotStyleKey, number>;
export type BotVisibility = "public" | "private";

export interface BotOpening {
  opening_id: string;
  color: PlayerColor;
  weight: number;
  name?: string;
  eco?: string;
}

export interface OpeningSearchResult {
  id: string;
  name: string;
  eco: string;
}

export interface BotProfile {
  id: string;
  name: string;
  description: string;
  avatar: string;
  target_elo: number;
  style: BotStyle;
  openings: BotOpening[];
  phrases: Record<string, string>;
  visibility: BotVisibility;
  owner_id: string | null;
  can_edit: boolean;
  can_delete: boolean;
  created_at: string;
  updated_at: string;
}

export type BotDraft = Pick<
  BotProfile,
  "name" | "description" | "avatar" | "target_elo" | "style" | "openings" | "phrases"
>;

export interface BotGame {
  fen: string;
  history: string[];
  player_color: PlayerColor;
  bot: BotProfile;
  turn: PlayerColor;
  status: string;
  result: string | null;
  last_move_uci: string | null;
  bot_message: string | null;
  pgn: string | null;
  llm_commentary_enabled: boolean;
  llm_commentary: string | null;
}
