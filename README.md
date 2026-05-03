# Api_Sodex_Trader

Sodex Trader API implementation and trading bot.

## Setup

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file based on the environment variables needed in `config.py`:
   - `SODEX_WALLET`
   - `SODEX_API_KEY`
   - `SODEX_API_KEY_NAME`
   - `SODEX_PRIVATE_KEY`
   - `SODEX_TESTNET`

## Running the Bot

To run the main bot:
```bash
python main.py
```

To run the dashboard:
```bash
python run_dashboard.py
```
