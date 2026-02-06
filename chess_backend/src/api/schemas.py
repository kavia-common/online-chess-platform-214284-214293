"""Pydantic schemas for the chess REST API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Color = Literal["white", "black"]
PieceType = Literal["pawn", "rook", "knight", "bishop", "queen", "king"]
GameStatus = Literal["in_progress"]


class PieceSchema(BaseModel):
    """A chess piece."""

    type: PieceType = Field(..., description="Piece type.")
    color: Color = Field(..., description="Piece color.")


class BoardItemSchema(BaseModel):
    """An occupied board square."""

    position: str = Field(..., description="Algebraic coordinate, e.g. 'e2'.")
    piece: PieceSchema = Field(..., description="Piece at that square.")


class GameStateSchema(BaseModel):
    """Current game state."""

    board: List[BoardItemSchema] = Field(
        ...,
        description="List of occupied squares (sparse board representation).",
    )
    current_turn: Color = Field(..., description="Whose turn it is to move.")
    game_status: GameStatus = Field(..., description="Game status (MVP: only 'in_progress').")


class MoveRequestSchema(BaseModel):
    """Request body for POST /move."""

    from_: str = Field(..., alias="from", description="From square in algebraic form, e.g. 'e2'.")
    to: str = Field(..., description="To square in algebraic form, e.g. 'e4'.")
    promotion: Optional[str] = Field(
        None,
        description="Optional promotion piece code when pawn reaches last rank: one of q,r,b,n.",
        examples=["q"],
    )

    class Config:
        populate_by_name = True


class MoveHistoryItemSchema(BaseModel):
    """One move in move history."""

    moveNumber: int = Field(..., description="Full move number (increments after black move).")
    color: Color = Field(..., description="Mover color.")
    from_: str = Field(..., alias="from", description="From square.")
    to: str = Field(..., description="To square.")
    capture: bool = Field(..., description="Whether the move captured a piece.")
    promotion: Optional[str] = Field(None, description="Promotion code if pawn was promoted (q,r,b,n).")
    piece: PieceSchema = Field(..., description="The moved piece type and color (pre-promotion piece).")

    class Config:
        populate_by_name = True


class MoveResponseSchema(BaseModel):
    """Response for a successfully applied move."""

    state: GameStateSchema = Field(..., description="Updated game state after move.")
    last_move: MoveHistoryItemSchema = Field(..., description="The move that was just applied.")


class HistoryResponseSchema(BaseModel):
    """Response for GET /history."""

    history: List[MoveHistoryItemSchema] = Field(..., description="Chronological move list.")


class RestartResponseSchema(BaseModel):
    """Response for POST /restart."""

    state: GameStateSchema = Field(..., description="Reset game state.")
    history: List[MoveHistoryItemSchema] = Field(..., description="Cleared history (empty list).")
