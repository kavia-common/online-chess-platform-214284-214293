"""
Chess engine module for a single in-memory shared game.

This MVP engine supports:
- Standard initial position
- Turn enforcement
- Basic per-piece legal move validation (no castling/en-passant/check validation)
- Pawn double move from starting rank, diagonal captures, and simple promotion
- Move history recording

Board representation:
- 8x8 list indexed as board[row][col], where row=0 is rank 8, row=7 is rank 1
- Algebraic coordinates are used at the API boundary (e.g., "e2" -> (row=6, col=4))
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

Color = Literal["white", "black"]
PieceType = Literal["pawn", "rook", "knight", "bishop", "queen", "king"]
GameStatus = Literal["in_progress"]


@dataclass(frozen=True)
class Piece:
    """A chess piece on the board."""

    type: PieceType
    color: Color

    def to_dict(self) -> Dict[str, Any]:
        """Convert piece to JSON-serializable dict."""
        return {"type": self.type, "color": self.color}


@dataclass
class MoveRecord:
    """Represents a single move in chronological history."""

    moveNumber: int
    color: Color
    from_square: str
    to_square: str
    capture: bool
    promotion: Optional[str]
    piece: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert history record to JSON-serializable dict."""
        data: Dict[str, Any] = {
            "moveNumber": self.moveNumber,
            "color": self.color,
            "from": self.from_square,
            "to": self.to_square,
            "capture": self.capture,
            "piece": self.piece,
        }
        if self.promotion:
            data["promotion"] = self.promotion
        return data


class IllegalMoveError(ValueError):
    """Raised when a proposed move is illegal for the current state."""


class ChessGame:
    """Single-game in-memory chess state and move application."""

    def __init__(self) -> None:
        self.board: List[List[Optional[Piece]]] = [[None for _ in range(8)] for _ in range(8)]
        self.current_turn: Color = "white"
        self.game_status: GameStatus = "in_progress"
        self.history: List[MoveRecord] = []
        self.restart()

    def restart(self) -> None:
        """Reset board, turn, status, and history to the standard initial position."""
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_turn = "white"
        self.game_status = "in_progress"
        self.history = []

        # Place pieces.
        # Row mapping: row 0 = rank 8 (black back rank), row 7 = rank 1 (white back rank)
        back_rank: List[PieceType] = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]

        # Black pieces
        for col, p in enumerate(back_rank):
            self.board[0][col] = Piece(type=p, color="black")
        for col in range(8):
            self.board[1][col] = Piece(type="pawn", color="black")

        # White pieces
        for col in range(8):
            self.board[6][col] = Piece(type="pawn", color="white")
        for col, p in enumerate(back_rank):
            self.board[7][col] = Piece(type=p, color="white")

    def get_state(self) -> Dict[str, Any]:
        """Return JSON-serializable game state."""
        return {
            "board": self._board_to_response(),
            "current_turn": self.current_turn,
            "game_status": self.game_status,
        }

    def get_history(self) -> List[Dict[str, Any]]:
        """Return JSON-serializable move history."""
        return [m.to_dict() for m in self.history]

    def apply_move(self, from_sq: str, to_sq: str, promotion: Optional[str] = None) -> MoveRecord:
        """Validate and apply a move, updating board and history.

        Raises:
            IllegalMoveError: if the move is not legal under MVP rules.
        """
        if self.game_status != "in_progress":
            raise IllegalMoveError("Game is not in progress.")

        if from_sq == to_sq:
            raise IllegalMoveError("from and to squares must be different.")

        fr = algebraic_to_index(from_sq)
        to = algebraic_to_index(to_sq)

        piece = self.board[fr[0]][fr[1]]
        if piece is None:
            raise IllegalMoveError(f"No piece at {from_sq}.")
        if piece.color != self.current_turn:
            raise IllegalMoveError(f"It is {self.current_turn}'s turn.")

        target = self.board[to[0]][to[1]]
        if target is not None and target.color == piece.color:
            raise IllegalMoveError("Cannot capture your own piece.")

        capture = target is not None

        self._validate_piece_move(piece=piece, fr=fr, to=to, capture=capture, promotion=promotion)

        # Execute move
        self.board[to[0]][to[1]] = piece
        self.board[fr[0]][fr[1]] = None

        # Apply promotion (only for pawn reaching last rank)
        promotion_applied: Optional[str] = None
        if piece.type == "pawn" and (to[0] == 0 or to[0] == 7):
            prom = (promotion or "q").lower()
            if prom not in ("q", "r", "b", "n"):
                raise IllegalMoveError("Invalid promotion piece. Use one of: q, r, b, n.")
            new_type: PieceType = {
                "q": "queen",
                "r": "rook",
                "b": "bishop",
                "n": "knight",
            }[prom]
            self.board[to[0]][to[1]] = Piece(type=new_type, color=piece.color)
            promotion_applied = prom

        # Record history
        move_number = (len(self.history) // 2) + 1
        record = MoveRecord(
            moveNumber=move_number,
            color=piece.color,
            from_square=from_sq,
            to_square=to_sq,
            capture=capture,
            promotion=promotion_applied,
            piece=piece.to_dict(),
        )
        self.history.append(record)

        # Toggle turn
        self.current_turn = "black" if self.current_turn == "white" else "white"
        return record

    def _board_to_response(self) -> List[Dict[str, Any]]:
        """Serialize board to a list of occupied squares with algebraic positions.

        Output shape is stable for the frontend:
          [{ position: "e2", piece: {type, color} }, ...]
        """
        items: List[Dict[str, Any]] = []
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece is None:
                    continue
                items.append(
                    {
                        "position": index_to_algebraic((row, col)),
                        "piece": piece.to_dict(),
                    }
                )
        return items

    def _validate_piece_move(
        self,
        piece: Piece,
        fr: Tuple[int, int],
        to: Tuple[int, int],
        capture: bool,
        promotion: Optional[str],
    ) -> None:
        """Validate a move by piece type with MVP rules (no check validation)."""
        dr = to[0] - fr[0]
        dc = to[1] - fr[1]

        if piece.type == "pawn":
            self._validate_pawn_move(piece, fr, to, dr, dc, capture, promotion)
            return

        if piece.type == "knight":
            if (abs(dr), abs(dc)) not in ((1, 2), (2, 1)):
                raise IllegalMoveError("Illegal knight move.")
            return

        if piece.type == "bishop":
            if abs(dr) != abs(dc) or dr == 0:
                raise IllegalMoveError("Illegal bishop move.")
            self._require_clear_path(fr, to)
            return

        if piece.type == "rook":
            if not (dr == 0 or dc == 0):
                raise IllegalMoveError("Illegal rook move.")
            if dr == 0 and dc == 0:
                raise IllegalMoveError("Illegal rook move.")
            self._require_clear_path(fr, to)
            return

        if piece.type == "queen":
            is_diag = abs(dr) == abs(dc) and dr != 0
            is_straight = (dr == 0) != (dc == 0)
            if not (is_diag or is_straight):
                raise IllegalMoveError("Illegal queen move.")
            self._require_clear_path(fr, to)
            return

        if piece.type == "king":
            if max(abs(dr), abs(dc)) != 1:
                raise IllegalMoveError("Illegal king move.")
            return

        raise IllegalMoveError("Unknown piece type.")

    def _validate_pawn_move(
        self,
        piece: Piece,
        fr: Tuple[int, int],
        to: Tuple[int, int],
        dr: int,
        dc: int,
        capture: bool,
        promotion: Optional[str],
    ) -> None:
        """Validate pawn movement and captures (no en-passant)."""
        direction = -1 if piece.color == "white" else 1  # white moves "up" (toward row 0)
        start_row = 6 if piece.color == "white" else 1

        # Promotion constraints are validated only when reaching last rank; promotion parameter is optional.
        if promotion is not None and (to[0] not in (0, 7)):
            raise IllegalMoveError("Promotion is only allowed when pawn reaches last rank.")

        # Captures: one step diagonally forward
        if capture:
            if dr != direction or abs(dc) != 1:
                raise IllegalMoveError("Illegal pawn capture.")
            return

        # Non-capturing pawn moves must stay in same file
        if dc != 0:
            raise IllegalMoveError("Illegal pawn move (pawns move straight unless capturing).")

        # One step forward
        if dr == direction:
            if self.board[to[0]][to[1]] is not None:
                raise IllegalMoveError("Pawn move blocked.")
            return

        # Two steps forward from start rank, must be clear
        if fr[0] == start_row and dr == 2 * direction:
            intermediate = (fr[0] + direction, fr[1])
            if self.board[intermediate[0]][intermediate[1]] is not None:
                raise IllegalMoveError("Pawn move blocked.")
            if self.board[to[0]][to[1]] is not None:
                raise IllegalMoveError("Pawn move blocked.")
            return

        raise IllegalMoveError("Illegal pawn move.")

    def _require_clear_path(self, fr: Tuple[int, int], to: Tuple[int, int]) -> None:
        """Ensure all intermediate squares between fr and to are empty (for sliders)."""
        dr = to[0] - fr[0]
        dc = to[1] - fr[1]

        step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
        step_c = 0 if dc == 0 else (1 if dc > 0 else -1)

        r = fr[0] + step_r
        c = fr[1] + step_c
        while (r, c) != to:
            if self.board[r][c] is not None:
                raise IllegalMoveError("Path is blocked.")
            r += step_r
            c += step_c


def algebraic_to_index(square: str) -> Tuple[int, int]:
    """Convert algebraic coordinate (e.g., 'e2') to board indices (row, col)."""
    if not isinstance(square, str) or len(square) != 2:
        raise IllegalMoveError("Square must be in algebraic form like 'e2'.")
    file_char = square[0].lower()
    rank_char = square[1]

    if file_char < "a" or file_char > "h":
        raise IllegalMoveError("File must be between a and h.")
    if rank_char < "1" or rank_char > "8":
        raise IllegalMoveError("Rank must be between 1 and 8.")

    col = ord(file_char) - ord("a")
    rank = int(rank_char)
    row = 8 - rank
    return (row, col)


def index_to_algebraic(idx: Tuple[int, int]) -> str:
    """Convert board indices (row, col) to algebraic coordinate (e.g., (6,4) -> 'e2')."""
    row, col = idx
    if not (0 <= row <= 7 and 0 <= col <= 7):
        raise IllegalMoveError("Index out of bounds.")
    file_char = chr(ord("a") + col)
    rank_char = str(8 - row)
    return f"{file_char}{rank_char}"


# Module-level singleton game store (single shared game)
GAME = ChessGame()
"""Global in-memory singleton game state for this backend instance."""
