
import aiohttp
import asyncio
from config import CRYPTOBOT_TOKEN

class CryptoBotAPI:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://pay.crypt.bot/api"

    async def create_invoice(self, amount, description="Пополнение баланса", currency_type="USDT"):
        """Создать инвойс для пополнения"""
        url = f"{self.base_url}/createInvoice"
        headers = {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json"
        }

        data = {
            "asset": currency_type,
            "amount": str(round(amount, 2)),
            "description": description,
            "paid_btn_name": "callback",
            "paid_btn_url": "https://t.me/MoonCasino777_bot"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            return result["result"]
                    else:
                        print(f"CryptoBot API Error: {response.status}")
                        error_text = await response.text()
                        print(f"Error details: {error_text}")
        except Exception as e:
            print(f"Exception in create_invoice: {e}")

        return None

    async def get_invoice(self, invoice_id):
        """Получить информацию об инвойсе"""
        url = f"{self.base_url}/getInvoices"
        headers = {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json"
        }

        data = {"invoice_ids": invoice_id if isinstance(invoice_id, list) else [invoice_id]}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok") and result.get("result", {}).get("items"):
                            return result["result"]["items"][0]
                    else:
                        print(f"Get invoice error: {response.status}")
        except Exception as e:
            print(f"Exception in get_invoice: {e}")

        return None

    async def transfer(self, user_id, amount, asset="USDT", comment="Выплата из NN | DICE WIN"):
        """Перевод средств пользователю"""
        url = f"{self.base_url}/transfer"
        headers = {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json"
        }

        # Уникальный ID для предотвращения дублирования
        spend_id = f"nndice_{user_id}_{int(amount*100)}_{hash(str(user_id) + str(amount))}"

        data = {
            "user_id": int(user_id),
            "asset": asset,
            "amount": str(round(amount, 2)),
            "spend_id": spend_id
            # Убираем comment из-за ограничения для новых приложений (30 дней)
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            return result["result"]
                    else:
                        print(f"Transfer error: {response.status}")
                        error_text = await response.text()
                        print(f"Transfer error details: {error_text}")
        except Exception as e:
            print(f"Exception in transfer: {e}")

        return None

    async def get_me(self):
        """Получить информацию о приложении"""
        url = f"{self.base_url}/getMe"
        headers = {
            "Crypto-Pay-API-Token": self.token
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            return result["result"]
        except Exception as e:
            print(f"Exception in get_me: {e}")

        return None

    async def get_balance(self):
        """Получить баланс приложения"""
        url = f"{self.base_url}/getBalance"
        headers = {
            "Crypto-Pay-API-Token": self.token
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            return result["result"]
                    else:
                        print(f"Get balance error: {response.status}")
                        error_text = await response.text()
                        print(f"Balance error details: {error_text}")
        except Exception as e:
            print(f"Exception in get_balance: {e}")

        return None

crypto_bot = CryptoBotAPI(CRYPTOBOT_TOKEN)

# Функция для тестирования подключения
async def test_cryptobot_connection():
    """Тестирует подключение к CryptoBot API"""
    try:
        me = await crypto_bot.get_me()
        if me:
            print(f"✅ CryptoBot подключен: {me.get('name', 'Unknown')}")
            return True
        else:
            print("❌ Ошибка подключения к CryptoBot")
            return False
    except Exception as e:
        print(f"❌ Ошибка тестирования CryptoBot: {e}")
        return False
