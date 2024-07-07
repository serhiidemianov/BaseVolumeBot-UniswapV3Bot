# main.py
from uniswap_universal_router_decoder import FunctionRecipient, RouterCodec
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from web3 import Account, Web3
from web3.exceptions import InvalidAddress
from decimal import Decimal, getcontext
import time
import telebot

from asset import weth_address,pair_address,usdc_address, permit2_address, rpc_endpoint_base, rpc_endpoint_eth, chain_id, limit_buy_amount, limit_sell_amount, private_key, ur_address, weth_address, weth_abi, limit_buy_price, limit_sell_price, degen_abi, permit2_abi


w3base = Web3(Web3.HTTPProvider(rpc_endpoint_base))
w3eth = Web3(Web3.HTTPProvider(rpc_endpoint_eth))
account = Account.from_key(private_key)
minimal_pool_abi = [
    {
        "constant": True,
        "inputs": [],
        "name": "fee",
        "outputs": [{"internalType": "uint24", "name": "", "type": "uint24"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
        {
        "constant": True,
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            # other slot0 return values omitted for brevity
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
]
codec = RouterCodec()

# Check if the variable is a number
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    text = None
    
    if not args:
        text = "Please input command correctly. e.g: /buy 0x000000000000000 0.00001"
        await update.message.reply_text(text)
        return
    
    if args[0] is not None:
        if args[0].startswith("0x") is False:
            text = "Input Value Error. e.g : /buy 0x000000000000000 0.00001"
            await update.message.reply_text(text)
            return

    if args[1] is not None:
        if is_number(args[1]) is False:
            text = "Input Value Error. e.g : /buy 0x000000000000000 0.00001"
            await update.message.reply_text(text)
            return
        if is_number(args[1]) is True:
            text = args[1]

    if text is None:
       text = "No actions, invalid command"
       await update.message.reply_text(text)
       return
    
    try:
        await update.message.reply_text(f"Wait a moment")
        token_contract = w3base.eth.contract(address=args[0], abi=degen_abi)
        # Example logic, adjust according to your asset names
        print(f"buy action called")
        # limit_buy_amount = 1 * 10**13
        limit_buy_amount = int(float(text) * 10**18)
        print(limit_buy_amount)
        min_amount_out = 365 * 10**10
        degen_balance_old = token_contract.functions.balanceOf(account.address).call()
    
        path = [weth_address, 3000 ,args[0]]
        codec = RouterCodec()

        encoded_input = (
                codec
                .encode
                .chain()
                .wrap_eth(FunctionRecipient.ROUTER, limit_buy_amount)
                .v3_swap_exact_in(FunctionRecipient.SENDER, limit_buy_amount, min_amount_out, path, payer_is_sender=False)
                .build(codec.get_default_deadline())
        )
        
        trx_params = {
                "from": account.address,
                "to": ur_address,
                "gas": 500_000,
                "maxPriorityFeePerGas": w3base.eth.max_priority_fee,
                "maxFeePerGas": 100 * 10**9,
                "type": '0x2',
                "chainId": chain_id,
                "value": limit_buy_amount,
                "nonce": w3base.eth.get_transaction_count(account.address),
                "data": encoded_input,
        }

        raw_transaction = w3base.eth.account.sign_transaction(trx_params, account.key).rawTransaction
        print(f"raw_transaction: {raw_transaction}")
        trx_hash = w3base.eth.send_raw_transaction(raw_transaction)
                   
        await update.message.reply_text(f"You paied {text} ETH")
        w3base.eth.wait_for_transaction_receipt(trx_hash)
        degen_balance = token_contract.functions.balanceOf(account.address).call()
        trx_hash_hex = trx_hash.hex()  # Convert bytes to hexadecimal string
        await update.message.reply_text(f"Buy completed: {(degen_balance - degen_balance_old) / 10**18} Token received")
        await update.message.reply_text(f"You can check here. (https://basescan.org/tx/{trx_hash_hex})")
        print(w3base.eth.get_balance(account.address))
        print("buy completed")
    except (ValueError, InvalidAddress) as e:
        error_message = str(e)  # Convert the exception to a string to get the error message
        print(f"An error occurred: {error_message}")
        await update.message.reply_text(f"An error occurred: {error_message}")
        return
    
async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    text = None
    
    if not args:
        text = "Please input amount. e.g: /sell 0x000000000000000 0.1"
        await update.message.reply_text(text)
        return
    
    if args[0] is not None:
        if args[0].startswith("0x") is False:
            text = "Input Value Error. e.g : /sell 0x000000000000000 0.00001"
            await update.message.reply_text(text)
            return

    if args[1] is not None:
        if is_number(args[1]) is False:
            text = "Input Value Error. e.g : /sell 0x000000000000000 0.1"
            await update.message.reply_text(text)
            return
        if is_number(args[1]) is True:
            text = args[1]

    if text is None:
       text = "No actions, invalid command"
       await update.message.reply_text(text)
       return
    
    print(f"sell action called")
    
    token_contract = w3base.eth.contract(address=args[0], abi=degen_abi)
    amount_in = int(float(text) * 10**18)
    # approve Permit2 to UNI
    permit2_allowance = 2**256 - 1  # max
    print(f"approve")
    contract_function = token_contract.functions.approve(
            permit2_address,
            amount_in
    )

    estimated_gas = contract_function.estimate_gas({
        "from": account.address,
        "value": 0,  # Adjust if your function sends value
    })

    # Add a margin to the estimated gas (e.g., 20% more)
    gas_limit_with_margin = int(estimated_gas * 1.2)
    print("gas_limit_with_margin = ",gas_limit_with_margin)
    trx_params = contract_function.build_transaction(
            {
                "from": account.address,
                "gas": gas_limit_with_margin,
                "maxPriorityFeePerGas": w3base.eth.max_priority_fee,
                "maxFeePerGas": 100 * 10**9,
                "type": '0x2',
                "chainId": chain_id,
                "value": 0,
                "nonce": w3base.eth.get_transaction_count(account.address),
            }
        )
    raw_transaction = w3base.eth.account.sign_transaction(trx_params, account.key).rawTransaction
    trx_hash = w3base.eth.send_raw_transaction(raw_transaction)
    print(f"Permit2 UNI approve trx hash: {trx_hash.hex()}")
    w3base.eth.wait_for_transaction_receipt(trx_hash)
    print(
            "Permit2 Degen allowance:",
            token_contract.functions.allowance(account.address, permit2_address).call(),
    )

    try:
        await update.message.reply_text(f"Wait a moment")

        permit2_contract = w3base.eth.contract(address=permit2_address, abi=permit2_abi)

        p2_amount, p2_expiration, p2_nonce = permit2_contract.functions.allowance(
                account.address,
                args[0],
                ur_address
        ).call()
    

        # permit message
        allowance_amount = 2**160 - 1  # max/infinite
        permit_data, signable_message = codec.create_permit2_signable_message(
                args[0],
                allowance_amount,
                codec.get_default_expiration(),  # 30 days
                p2_nonce,
                ur_address,
                codec.get_default_deadline(),  # 180 seconds
                chain_id,
            )
        print("permit_data:", permit_data)
        print("signable_message:", signable_message)

        # Signing the message
        signed_message = account.sign_message(signable_message)
        # print("signed_message:", signed_message)

        # Building the Swap to sell UNI for USDT
        weth_contract = w3base.eth.contract(address=weth_address, abi=weth_abi)
        weth_balance_old = weth_contract.functions.balanceOf(account.address).call()

        min_amount_out = 415 * 10**6
        path = [args[0], 3000 ,weth_address]
        encoded_input = (
                codec
                .encode
                .chain()
                .permit2_permit(permit_data, signed_message)
                .v3_swap_exact_in(
                        FunctionRecipient.SENDER,
                        amount_in,
                        min_amount_out,
                        path,
                        payer_is_sender=True,
                )
                .build(codec.get_default_deadline())
            )

        trx_params = {
                "from": account.address,
                "to": ur_address,
                "gas": 500000,
                "maxPriorityFeePerGas": w3base.eth.max_priority_fee,
                "maxFeePerGas": 100 * 10**9,
                "type": '0x2',
                "chainId": chain_id,
                "value": 0,
                "nonce": w3base.eth.get_transaction_count(account.address),
                "data": encoded_input,
        }
        raw_transaction = w3base.eth.account.sign_transaction(trx_params, account.key).rawTransaction
        trx_hash = w3base.eth.send_raw_transaction(raw_transaction)
        await update.message.reply_text(f"You paied {text} Token")
        print(f"Trx Hash: {trx_hash.hex()}")
        w3base.eth.wait_for_transaction_receipt(trx_hash)
        
        # Checking the balances
        degen_balance = token_contract.functions.balanceOf(account.address).call()
        print("Degen Balance:", degen_balance / 10**18, "DEGEN")

        weth_balance = weth_contract.functions.balanceOf(account.address).call()
        print("WETH Balance:", weth_balance / 10**18, "WETH")

        trx_hash_hex = trx_hash.hex()  # Convert bytes to hexadecimal string
        await update.message.reply_text(f"Sell completed: {(weth_balance - weth_balance_old) / 10**18} WETH received")
        await update.message.reply_text(f"You can check here. (https://basescan.org/tx/{trx_hash_hex})")

        # Checking the new Permit2 allowance
        p2_amount, p2_expiration, p2_nonce = permit2_contract.functions.allowance(
                account.address,
                args[0],
                ur_address
        ).call()
    
        print("sell completed")
    except (ValueError, InvalidAddress) as e:
        error_message = str(e)  # Convert the exception to a string to get the error message
        print(f"An error occurred: {error_message}")
        await update.message.reply_text(f"An error occurred: {error_message}")
        return
    # Example logic, adjust according to your asset names

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    print("chat_id: " + str(chat_id))
    
    text = "\n◽️ Welcome to MyCryptoTradingBot. ◽️" + "\n\n"
    text += "This is a list of all the things I'm capable of at the moment. " + "\n\n"
    text += "Please add me to your group first before using any of my commands." + "\n\n"
    text += "- Type /buy <Token Address> <Amount> | to buy given Token with ETH" + "\n\n"
    text += "- Type /sell <Token Address> <Amount> | to sell given Token and earn WETH" + "\n\n"
    text += "- Type /help | to show all commands" + "\n\n"
    text += "Click here for a tutorial on how to set me up"

    await update.message.reply_text(text)

def get_degen_price():
    getcontext().prec = 18
    Q96 = Decimal(2**96)
    pool_contract = w3eth.eth.contract(address=usdc_address, abi=minimal_pool_abi)
    # Query for pool's fee tier

    slot0 = pool_contract.functions.slot0().call()
    liquidity = pool_contract.functions.liquidity().call()
    sqrtPriceX96 = Decimal(slot0[0])
    liquidity = Decimal(liquidity)


    # Calculating price per token
    price_per_token0 = (sqrtPriceX96 / Q96) ** 2
    price_per_token1 = 1 / price_per_token0 * 10**12
    # print(f"price of Token0 (WETH): {price_per_token0}")
    # print(f"price of Token1 (ETH Price): {price_per_token1}")

    pool_contract = w3base.eth.contract(address=pair_address, abi=minimal_pool_abi)
    # Query for pool's fee tier

    slot0 = pool_contract.functions.slot0().call()
    liquidity = pool_contract.functions.liquidity().call()
    sqrtPriceX96 = Decimal(slot0[0])
    liquidity = Decimal(liquidity)
    # print(f"Current sqrtPriceX96: {slot0[0]}")
    # print(f"Current liquidity: {liquidity}")




    # Calculating price per token
    price_per_token0 = (sqrtPriceX96 / Q96) ** 2
    degen_price = 1 / price_per_token0 * price_per_token1
    # print(f"price of Token0 (WETH): {price_per_token0}")
    # print(f"price of Token1 (DEGEN): {degen_price}")
    fee_tier = pool_contract.functions.fee().call()

    # print(f"Pool's fee tier: {fee_tier}")
    return degen_price
# Example usage
if __name__ == "__main__":
    
    telegram_token = '7139865116:AAG-fZTEI16pCfaqrGhLb_hSNf40vZagbNYABC'
    bot = telebot.TeleBot(telegram_token)
    updates = bot.get_updates()
    # chat_id = updates[0].message.chat.id
    
    # print("chat_id: " + str(chat_id))
            
    app = ApplicationBuilder().token(
        telegram_token).read_timeout(30).write_timeout(30).build()

    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("help", bot_help))
   
    app.run_polling()