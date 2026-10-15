"""Reading Saldo Palet (the supplier pallet balance app) over its API."""

from dataclasses import dataclass
from datetime import date

import httpx

from app.core.config import settings
from app.core.exc import BadRequestException

TIMEOUT_SECONDS = 20


class SaldoPaletUnavailable(BadRequestException):
    """Saldo Palet could not be read; the message says why, in Polish."""


@dataclass(frozen=True)
class SaldoTransaction:
    type: str  # RECEIPT (IN), ISSUE (OUT), CORRECTION (signed)
    quantity: int
    unit: str


class SaldoPaletClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    async def transactions_added_on(self, day: date) -> list[SaldoTransaction]:
        """The transactions entered on a day ("Data_dodania"), every area."""
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=TIMEOUT_SECONDS
            ) as http:
                login = await http.post(
                    "/auth/login",
                    json={"username": self.username, "password": self.password},
                )
                if login.status_code != 200:
                    raise SaldoPaletUnavailable(
                        "Saldo Palet nie przyjęło logowania konta MONOLIT"
                        f" (HTTP {login.status_code})"
                    )
                token = login.json()["access_token"]
                response = await http.get(
                    "/reports/transactions",
                    params={"added_on": day.isoformat()},
                    headers={"Authorization": f"Bearer {token}"},
                )
                if response.status_code != 200:
                    raise SaldoPaletUnavailable(
                        f"Saldo Palet odpowiedziało błędem (HTTP {response.status_code})"
                    )
                return [
                    SaldoTransaction(
                        type=row["type"],
                        quantity=int(row["quantity"]),
                        unit=row["unit"],
                    )
                    for row in response.json()
                ]
        except httpx.HTTPError as error:
            raise SaldoPaletUnavailable(
                f"Brak połączenia z Saldem Palet ({type(error).__name__})"
            ) from error
        except (KeyError, TypeError, ValueError) as error:
            raise SaldoPaletUnavailable(
                "Saldo Palet zwróciło nieoczekiwane dane"
            ) from error


def configured_client() -> SaldoPaletClient | None:
    """The client from the settings, or None while the URL is not set."""
    app = settings.app
    if not app.SALDO_PALET_URL:
        return None
    return SaldoPaletClient(
        app.SALDO_PALET_URL, app.SALDO_PALET_USERNAME, app.SALDO_PALET_PASSWORD
    )
