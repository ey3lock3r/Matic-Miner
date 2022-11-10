import asyncio
import logging
import requests
import time
import traceback
from web3 import Web3
from web3.middleware import geth_poa_middleware

class MinerBot():
    def __init__(self, rpc, gas_api, miner_abi, miner_cont, transaction, pkey, polyscan_token, interval, logger=None):
        self.gas_api = gas_api + polyscan_token
        self.pkey = pkey
        self.interval = interval
        self.wait_count = 0
        self.gasprice = 0

        self.transaction = transaction
        self.hash = None

        self.logger = (logging.getLogger(logger) if isinstance(logger,str) else logger)
        if self.logger is None:
            self.logger = logging.getLogger(__name__)
        
        web3 = Web3(Web3.HTTPProvider(rpc))
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.account = web3.eth.account.privateKeyToAccount(pkey)
        self.miner = web3.eth.contract(address=Web3.toChecksumAddress(miner_cont), abi=miner_abi)
        self.web3 = web3

        self.logger.info('Miner Bot initialized!')

    def send_transaction(self, tx):
        # sign the transaction
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.pkey)
        # send the transaction
        self.hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        self.logger.info(f'Tx Hash: {self.hash.hex()}')
        self.wait_count = 0

    async def execute_trans(self):
        self.logger.info('>'*70)
        self.logger.info('Executing...')
        loop = asyncio.get_event_loop()
        web3 = self.web3  
        account = self.account
        mminer = self.miner

        if pendNonce > nonce and self.wait_count < 3:
            self.logger.info(f'There are pending transactions [{pendNonce}, {nonce}] ... waited {self.wait_count}x!')
            self.wait_count += 1
            return

        pendNonce = web3.eth.getTransactionCount(account.address, 'pending')
        nonce = web3.eth.getTransactionCount(account.address)
        gasp = requests.get(self.gas_api).json()['result']['SafeGasPrice']

        if gasp > '90':
            return
        
        if self.wait_count == 0:
            self.gasprice = gasp
        else:
            gasp = self.gasprice
        
        balance = loop.run_in_executor(None, web3.eth.getBalance, account.address)
        gasPrice = loop.run_in_executor(None, web3.toWei, gasp, 'gwei')
        eggs = loop.run_in_executor(None, mminer.functions.getMyEggs().call, {'from': account.address})

        balance = await balance
        eggs = await eggs
        maticBal = loop.run_in_executor(None, web3.fromWei, balance, "ether")
        mined_matic = loop.run_in_executor(None, mminer.functions.calculateEggSell(eggs).call)

        maticBal = await maticBal
        gasPrice = await gasPrice
        mined_matic = await mined_matic
        mined_matic_1 = web3.fromWei(mined_matic, "ether")

        self.logger.info(f'Balance: {maticBal}')
        self.logger.info(f'Mined Matic: {mined_matic_1}')
        self.logger.info(f'Gas Price: {gasp}')
        self.logger.info(f'Nonce: {nonce}')
        
        tx = {
            'nonce': nonce,
            'from': account.address,
            'gasPrice': gasPrice
        }
        tx = {**self.transaction, **tx}

        # >>>> Autocompound
        if maticBal >= 0.01:
            # Calculate Gas Fee
            estGas = mminer.functions.hatchEggs(Web3.toChecksumAddress(account.address)).estimateGas(tx)
            gasFee = estGas * gasPrice
            # tx['gas'] = estGas

            if mined_matic - gasFee > gasFee:
                gasFee_1 = web3.fromWei(gasFee, "ether")
                self.logger.info(f'Gas Fee: {gasFee_1}')
                self.logger.info('Autocompounding...')
                # build the transaction
                tx_built = mminer.functions.hatchEggs(Web3.toChecksumAddress(account.address)).buildTransaction(tx)
                self.send_transaction(tx_built)

        # >>>> Withdraw Matic
        else:
            # Calculate Gas & Dev Fee
            estGas = loop.run_in_executor(None, mminer.functions.sellEggs().estimateGas, tx)
            devFee = loop.run_in_executor(None, mminer.functions.devFee(eggs).call)
            gasFee = await estGas * gasPrice
            devFee = await devFee
            
            # devFeeMatic = mminer.functions.calculateEggSell(devFee).call()
            earned_matic = mminer.functions.calculateEggSell(eggs - devFee).call()

            actualDevFee = mined_matic - earned_matic
            totalFees = gasFee + actualDevFee

            if earned_matic - gasFee > totalFees:
                gasFee_1 = loop.run_in_executor(None, web3.fromWei, gasFee, "ether")
                actualDevFee_1 = loop.run_in_executor(None, web3.fromWei, actualDevFee, "ether")
                gasFee_1 = await gasFee_1
                actualDevFee_1 = await actualDevFee_1
                self.logger.info(f'Gas Fee: {gasFee_1}')
                self.logger.info(f'Dev Fee: {actualDevFee_1}')
                self.logger.info('Withdrawing...')
                # build the transaction
                tx_built = mminer.functions.sellEggs().buildTransaction(tx)
                self.send_transaction(tx_built)

    async def start(self, interval):
        
        while True:
            # sleep until the next whole interval
            await asyncio.sleep(interval - time.time() % interval)

            try:
                await self.execute_trans()
            except Exception as E:
                self.logger.info(f'Error: {E}')
                self.logger.debug(traceback.print_exc())

    def run(self):
        """Wrapper for start to run without additional libraries for managing asynchronous"""

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.start(self.interval))

        except KeyboardInterrupt:
            self.logger.info('Gracefully exit')

        finally:
            loop.close()
            self.logger.info('Program finished')
