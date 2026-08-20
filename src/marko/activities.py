from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from marko.money import Money, decimal_value


class ActivityKind(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE = "fee"
    TAX = "tax"
    DELIVERY_IN = "delivery_in"
    DELIVERY_OUT = "delivery_out"
    CASH_TRANSFER_IN = "cash_transfer_in"
    CASH_TRANSFER_OUT = "cash_transfer_out"
    POSITION_TRANSFER_IN = "position_transfer_in"
    POSITION_TRANSFER_OUT = "position_transfer_out"
    FX_CONVERSION = "fx_conversion"
    SPLIT = "split"
    SPINOFF = "spinoff"
    AMORTIZATION = "amortization"


_TRADE_KINDS = {ActivityKind.BUY, ActivityKind.SELL}
_POSITION_KINDS = _TRADE_KINDS | {
    ActivityKind.DELIVERY_IN,
    ActivityKind.DELIVERY_OUT,
    ActivityKind.POSITION_TRANSFER_IN,
    ActivityKind.POSITION_TRANSFER_OUT,
    ActivityKind.SPINOFF,
}
_CASH_KINDS = {
    ActivityKind.DEPOSIT,
    ActivityKind.WITHDRAWAL,
    ActivityKind.BUY,
    ActivityKind.SELL,
    ActivityKind.DIVIDEND,
    ActivityKind.INTEREST,
    ActivityKind.FEE,
    ActivityKind.TAX,
    ActivityKind.CASH_TRANSFER_IN,
    ActivityKind.CASH_TRANSFER_OUT,
    ActivityKind.FX_CONVERSION,
    ActivityKind.AMORTIZATION,
}


@dataclass(frozen=True, slots=True)
class Activity:
    activity_id: str
    kind: ActivityKind
    account_id: str
    effective_at: datetime
    recorded_at: datetime
    gross_amount: Money | None = None
    instrument_id: str | None = None
    quantity: Decimal | None = None
    fee: Money | None = None
    tax: Money | None = None
    cost_basis: Money | None = None
    counter_amount: Money | None = None
    related_account_id: str | None = None
    related_activity_id: str | None = None
    related_instrument_id: str | None = None
    ratio: Decimal | None = None
    external_id: str | None = None
    correction_of: str | None = None
    is_reversal: bool = False
    sequence: int = 0

    def __post_init__(self) -> None:
        if not self.activity_id.strip() or not self.account_id.strip():
            raise ValueError("activity_id e account_id são obrigatórios")
        if self.sequence < 0:
            raise ValueError("sequence não pode ser negativa")
        if self.effective_at.tzinfo is None or self.recorded_at.tzinfo is None:
            raise ValueError("timestamps de activity precisam de timezone")
        if self.recorded_at < self.effective_at:
            raise ValueError("recorded_at não pode preceder effective_at")
        if self.quantity is not None:
            object.__setattr__(self, "quantity", decimal_value(self.quantity))
        if self.ratio is not None:
            object.__setattr__(self, "ratio", decimal_value(self.ratio))
        if self.kind is ActivityKind.SPLIT:
            if not self.instrument_id or self.ratio is None or self.ratio <= 0:
                raise ValueError("split exige instrumento e ratio positivo")
            if self.quantity is not None or self.gross_amount is not None:
                raise ValueError("split não recebe quantidade nem caixa")
        elif self.kind in _POSITION_KINDS:
            if not self.instrument_id or self.quantity is None or self.quantity <= 0:
                raise ValueError("activity de posição exige instrumento e quantidade positiva")
        elif (self.quantity is not None or self.instrument_id is not None) and self.kind not in {
            ActivityKind.DIVIDEND,
            ActivityKind.AMORTIZATION,
        }:
            raise ValueError("instrumento/quantidade não se aplica a este tipo de activity")
        if self.kind in _CASH_KINDS:
            if self.gross_amount is None or self.gross_amount.amount <= 0:
                raise ValueError("activity de caixa exige gross_amount positivo")
        elif self.kind is not ActivityKind.SPLIT and self.gross_amount is not None:
            raise ValueError("delivery não movimenta caixa")
        if self.kind in _TRADE_KINDS and self.gross_amount is None:
            raise ValueError("trade exige gross_amount")
        for charge in (self.fee, self.tax):
            if charge is not None:
                if charge.amount < 0:
                    raise ValueError("taxas e impostos não podem ser negativos")
                if self.gross_amount is None:
                    raise ValueError("taxas e impostos exigem gross_amount")
                self.gross_amount._check_currency(charge)
        if self.cost_basis is not None and (
            self.cost_basis.amount < 0
            or self.kind
            not in {
                ActivityKind.DELIVERY_IN,
                ActivityKind.POSITION_TRANSFER_IN,
                ActivityKind.SPINOFF,
            }
        ):
            raise ValueError("cost_basis só se aplica a entrada de posição")
        if self.kind is ActivityKind.FX_CONVERSION:
            assert self.gross_amount is not None
            if self.counter_amount is None or self.counter_amount.amount <= 0:
                raise ValueError("conversão FX exige counter_amount positivo")
            if self.counter_amount.currency == self.gross_amount.currency:
                raise ValueError("conversão FX exige moedas diferentes")
            if self.ratio is None or self.ratio <= 0:
                raise ValueError("conversão FX exige taxa positiva")
        elif self.counter_amount is not None:
            raise ValueError("counter_amount só se aplica a conversão FX")
        if self.kind in {
            ActivityKind.CASH_TRANSFER_IN,
            ActivityKind.CASH_TRANSFER_OUT,
            ActivityKind.POSITION_TRANSFER_IN,
            ActivityKind.POSITION_TRANSFER_OUT,
        } and (not self.related_account_id or not self.related_activity_id):
            raise ValueError("transferência exige conta e activity relacionadas")
        if self.kind is ActivityKind.SPINOFF and not self.related_instrument_id:
            raise ValueError("spinoff exige o instrumento de origem")
        if self.is_reversal and not self.correction_of:
            raise ValueError("reversal exige correction_of")

    def cash_effect(self) -> Money | None:
        effects = self.cash_effects()
        return effects[0] if len(effects) == 1 else None

    def cash_effects(self) -> tuple[Money, ...]:
        if self.gross_amount is None:
            return ()
        if self.kind is ActivityKind.FX_CONVERSION:
            assert self.counter_amount is not None
            effects = (-self.gross_amount, self.counter_amount)
            return tuple(-effect for effect in effects) if self.is_reversal else effects
        fee = self.fee or Money.zero(self.gross_amount.currency)
        tax = self.tax or Money.zero(self.gross_amount.currency)
        if self.kind in {
            ActivityKind.DEPOSIT,
            ActivityKind.DIVIDEND,
            ActivityKind.INTEREST,
            ActivityKind.SELL,
            ActivityKind.CASH_TRANSFER_IN,
            ActivityKind.AMORTIZATION,
        }:
            effect = self.gross_amount - fee - tax
        elif self.kind is ActivityKind.BUY:
            effect = -(self.gross_amount + fee + tax)
        else:
            effect = -self.gross_amount
        return (-effect,) if self.is_reversal else (effect,)

    def position_effect(self) -> Decimal:
        if self.quantity is None:
            return Decimal(0)
        if self.kind in {
            ActivityKind.BUY,
            ActivityKind.DELIVERY_IN,
            ActivityKind.POSITION_TRANSFER_IN,
            ActivityKind.SPINOFF,
        }:
            effect = self.quantity
        elif self.kind in {
            ActivityKind.SELL,
            ActivityKind.DELIVERY_OUT,
            ActivityKind.POSITION_TRANSFER_OUT,
        }:
            effect = -self.quantity
        else:
            effect = Decimal(0)
        return -effect if self.is_reversal else effect
