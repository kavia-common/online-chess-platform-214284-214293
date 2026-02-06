from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    GameStateSchema,
    HistoryResponseSchema,
    MoveRequestSchema,
    MoveResponseSchema,
    RestartResponseSchema,
)
from src.chess.engine import GAME, IllegalMoveError

openapi_tags = [
    {
        "name": "Health",
        "description": "Service health check.",
    },
    {
        "name": "Chess",
        "description": "Chess game endpoints for a single shared in-memory game.",
    },
]

app = FastAPI(
    title="Chess Backend API",
    description=(
        "FastAPI backend implementing an in-memory single-game chess engine.\n\n"
        "Notes (MVP):\n"
        "- Basic per-piece movement rules are enforced.\n"
        "- Castling, en-passant, and check/checkmate validation are not implemented.\n"
        "- State is stored in memory (single shared game instance)."
    ),
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# Allow React dev server to call the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"], summary="Health Check")
# PUBLIC_INTERFACE
def health_check() -> dict:
    """Backend health check endpoint.

    Returns:
        JSON object indicating the service is running.
    """
    return {"message": "Healthy"}


@app.get(
    "/state",
    response_model=GameStateSchema,
    tags=["Chess"],
    summary="Get current game state",
    description="Returns the current board (occupied squares), current_turn, and game_status.",
)
# PUBLIC_INTERFACE
def get_state() -> GameStateSchema:
    """Fetch current chess game state.

    Returns:
        GameStateSchema: The current game state.
    """
    return GameStateSchema.model_validate(GAME.get_state())


@app.post(
    "/move",
    response_model=MoveResponseSchema,
    tags=["Chess"],
    summary="Make a move",
    description=(
        "Apply a move for the current player.\n\n"
        "Move legality (MVP): per-piece movement patterns, path blocking, captures by opponent, "
        "pawn single/double moves, diagonal pawn captures, simple promotion.\n\n"
        "Not implemented: castling, en-passant, and check/checkmate validation."
    ),
)
# PUBLIC_INTERFACE
def post_move(payload: MoveRequestSchema) -> MoveResponseSchema:
    """Apply a chess move to the single shared in-memory game.

    Args:
        payload: MoveRequestSchema containing from/to squares and optional promotion.

    Returns:
        MoveResponseSchema: Updated state and last_move.

    Raises:
        HTTPException(400): If the move is illegal or malformed.
    """
    try:
        record = GAME.apply_move(
            from_sq=payload.from_,
            to_sq=payload.to,
            promotion=payload.promotion,
        )
    except IllegalMoveError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    state = GAME.get_state()
    return MoveResponseSchema(
        state=GameStateSchema.model_validate(state),
        last_move=record.to_dict(),
    )


@app.get(
    "/history",
    response_model=HistoryResponseSchema,
    tags=["Chess"],
    summary="Get move history",
    description="Returns the chronological move list with metadata.",
)
# PUBLIC_INTERFACE
def get_history() -> HistoryResponseSchema:
    """Fetch chronological move history.

    Returns:
        HistoryResponseSchema: A list of all moves made so far.
    """
    return HistoryResponseSchema.model_validate({"history": GAME.get_history()})


@app.post(
    "/restart",
    response_model=RestartResponseSchema,
    tags=["Chess"],
    summary="Restart the game",
    description="Resets to the initial chess position and clears move history.",
)
# PUBLIC_INTERFACE
def post_restart() -> RestartResponseSchema:
    """Restart the single shared game.

    Returns:
        RestartResponseSchema: Reset state and empty history.
    """
    GAME.restart()
    return RestartResponseSchema.model_validate({"state": GAME.get_state(), "history": []})
