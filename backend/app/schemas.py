"""API request/response models."""
from typing import Any, Dict

from pydantic import BaseModel, Field


class Item(BaseModel):
    description: str = ""
    quantity: float = 0
    unit_price: float = Field(0, alias="unit-price")

    model_config = {"populate_by_name": True}


class CreateInvoiceRequest(BaseModel):
    invoice_number: str = Field("", alias="invoice-number")
    client_name: str = Field("", alias="client-name")
    client_email: str = Field("", alias="client-email")
    client_address: str = Field("", alias="client-address")
    date: str = Field("", alias="date")
    work_from: str = Field("", alias="work-from")
    work_to: str = Field("", alias="work-to")
    deposit_date: str = Field("", alias="deposit-date")
    exchange_rate: float | None = Field(None, alias="exchange-rate")
    pesos: float | None = Field(None, alias="pesos")
    items: list[Item] = []
    due_date: str = Field("", alias="due-date")
    bank_info: str = Field("", alias="bank-info")

    model_config = {"populate_by_name": True}

    def to_service_data(self) -> Dict[str, Any]:
        """Dict shape expected by `invoice.build_invoice`."""
        return {
            "invoice-number": self.invoice_number,
            "client-name": self.client_name,
            "client-email": self.client_email,
            "client-address": self.client_address,
            "date": self.date,
            "work-from": self.work_from,
            "work-to": self.work_to,
            "deposit-date": self.deposit_date,
            "exchange-rate": self.exchange_rate,
            "pesos": self.pesos,
            "items": [
                {"description": i.description, "quantity": i.quantity, "unit-price": i.unit_price}
                for i in self.items
            ],
            "due-date": self.due_date,
            "bank-info": self.bank_info,
        }


class SendInvoiceRequest(BaseModel):
    to: str = Field("", alias="to")
    subject: str = Field("", alias="subject")

    model_config = {"populate_by_name": True}
