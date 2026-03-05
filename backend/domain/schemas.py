from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.enums import OrderStatus, PaymentStatus, PaymentType


class OrderBase(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Сумма заказа")


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    paid_amount: Optional[Decimal] = Field(None, ge=0, description="Оплаченная сумма")


class OrderResponse(OrderBase):
    id: int
    paid_amount: Decimal
    status: OrderStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentBase(BaseModel):
    order_id: int
    amount: Decimal = Field(..., gt=0, description="Сумма платежа")
    type: PaymentType


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    bank_status: Optional[str] = None
    bank_paid_at: Optional[datetime] = None
    error_message: Optional[str] = None


class PaymentResponse(PaymentBase):
    id: int
    status: PaymentStatus
    bank_payment_id: Optional[str] = None
    bank_status: Optional[str] = None
    bank_paid_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentRefund(BaseModel):
    payment_id: int


class BankPaymentCreateRequest(BaseModel):
    order_id: int
    amount: Decimal = Field(..., gt=0, description="Сумма платежа")


class BankPaymentCreateResponse(BaseModel):
    payment_id: str
    success: bool
    error: Optional[str] = None
    status: Optional[str] = "pending"
    requires_webhook: bool = True


class BankPaymentCheckRequest(BaseModel):
    bank_payment_id: str


class BankPaymentCheckResponse(BaseModel):
    payment_id: str
    amount: Decimal
    status: str
    paid_at: Optional[datetime] = None
    error: Optional[str] = None


class BankWebhookPayload(BaseModel):
    payment_id: str
    order_id: int
    amount: Decimal
    status: str
    paid_at: Optional[datetime] = None
    error: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class BankWebhookResponse(BaseModel):
    received: bool
    processed: bool
    message: str
