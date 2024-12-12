import asyncio
from datetime import datetime, timedelta
import json
import logging
from aiofile import async_open
from aiopath import AsyncPath

import aiohttp
import websockets
import names
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK

logging.basicConfig(level=logging.INFO)

class HttpError(Exception):
    pass

async def request(url: str) -> dict | str:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result
                else:
                    raise HttpError(f"Error: {resp.status} for URL {url}")
        except aiohttp.ClientConnectorError as err:
            raise HttpError(f"Connection error: {url}. Reason: {str(err)}")

async def get_exchange(currencies):
    try:
        response = await request(
            'https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5'
        )
        filtered_response = filter_currencies(response, currencies)
        return json.dumps(filtered_response, indent=2)
    except HttpError as err:
        logging.error(err)
        return str(err)

async def get_exchange_past_days(days, currencies):
    results = []
    for index_day in range(1, days + 1):
        d = datetime.now() - timedelta(days=index_day)
        shift = d.strftime("%d.%m.%Y")
        try:
            response = await request(
                f'https://api.privatbank.ua/p24api/exchange_rates?date={shift}'
            )
            rates = selected_rates(response, currencies)
            results.append({shift: rates})
        except HttpError as err:
            logging.error(err)
            results.append({shift: str(err)})
    return results

def selected_rates(data, currencies):
    try:
        rates = data["exchangeRate"]
        result = {}
        for currency in currencies:
            rate = next((rate for rate in rates if rate["currency"] == currency), None)
            if rate:
                result[currency] = {
                    "sale": rate.get("saleRate", "N/A"),
                    "purchase": rate.get("purchaseRate", "N/A"),
                }
            else:
                result[currency] = "No data"
        return result
    except KeyError as e:
        raise ValueError(f"Invalid response structure: {e}")

def filter_currencies(data, currencies):
    return [rate for rate in data if rate["ccy"] in currencies]

async def log_command_to_file(command: str, result: str):
    """Log a command and its result to a file."""
    log_path = AsyncPath("server.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with async_open(log_path, mode="a") as log_file:
        await log_file.write(f"[{timestamp}] Command: {command}\nResult:\n{result}\n\n")

class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            await asyncio.gather(*(client.send(message) for client in self.clients))

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distribute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distribute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            if message.startswith("exchange"):
                parts = message.split()
                if len(parts) == 1:
                    exchange = await get_exchange(["USD", "EUR"])
                    await log_command_to_file(message, exchange)  # Log the command
                    await self.send_to_clients(exchange)
                elif len(parts) == 2 and parts[1].isdigit():
                    days = int(parts[1])
                    if days < 1 or days > 10:
                        error_msg = "Error: Days must be between 1 and 10."
                        await log_command_to_file(message, error_msg)  # Log error
                        await self.send_to_clients(error_msg)
                    else:
                        exchange_past = await get_exchange_past_days(days, ["USD", "EUR"])
                        result = json.dumps(exchange_past, indent=2)
                        await log_command_to_file(message, result)  # Log the command
                        await self.send_to_clients(result)
                elif len(parts) > 2:
                    currencies = parts[2:]
                    days = int(parts[1]) if parts[1].isdigit() else 1
                    exchange_past = await get_exchange_past_days(days, currencies)
                    result = json.dumps(exchange_past, indent=2)
                    await log_command_to_file(message, result)  # Log the command
                    await self.send_to_clients(result)
                else:
                    error_msg = "Invalid command format."
                    await log_command_to_file(message, error_msg)  # Log error
                    await self.send_to_clients(error_msg)
            elif message == "Hello server":
                await self.send_to_clients("Hello, my customers!")
            else:
                await self.send_to_clients(f"{ws.name}: {message}")

async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8080):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    asyncio.run(main())
