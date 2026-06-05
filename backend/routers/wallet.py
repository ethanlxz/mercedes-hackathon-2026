"""
routers/wallet.py
-----------------
Routes related to the Mercedes Mobility Wallet.

Endpoints:
  GET  /wallet/balance  — return current balance
  POST /wallet/topup    — add funds to the wallet
  POST /wallet/charge   — deduct funds from the wallet
"""

from fastapi import APIRouter, HTTPException

from models.schemas import WalletChargeRequest, WalletTopUpRequest
from services.memory_service import load_memory, save_memory

router = APIRouter(
    prefix="/wallet",
    tags=["Wallet"],
)


@router.get("/balance")
def get_wallet_balance() -> dict:
    """Return the current mobility wallet balance."""
    memory = load_memory()
    return {"balance": memory["profile"]["wallet_balance"]}


@router.post("/topup")
def topup_wallet(request: WalletTopUpRequest) -> dict:
    """Add the specified amount to the mobility wallet."""
    memory = load_memory()
    memory["profile"]["wallet_balance"] += request.amount
    save_memory(memory)
    return {
        "status": "success",
        "new_balance": memory["profile"]["wallet_balance"],
        "message": f"Successfully topped up RM {request.amount:.2f} to mobility wallet.",
    }


@router.post("/charge")
def charge_wallet(request: WalletChargeRequest) -> dict:
    """
    Deduct the specified amount from the mobility wallet.
    Raises HTTP 400 if the balance is insufficient.
    """
    memory = load_memory()
    balance = memory["profile"]["wallet_balance"]

    if balance < request.amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient funds in mobility wallet.",
        )

    memory["profile"]["wallet_balance"] -= request.amount
    save_memory(memory)
    return {
        "status": "success",
        "new_balance": memory["profile"]["wallet_balance"],
        "message": f"Charged RM {request.amount:.2f} for: {request.reason}.",
    }
