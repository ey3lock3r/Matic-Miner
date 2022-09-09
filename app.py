# Loading an Environment Variable File with dotenv
from dotenv import load_dotenv
load_dotenv()

from Bot import MinerBot
import os
import yaml
import logging.config

def main():

    # Подгружаем конфиг
    with open('./config.yaml','r') as f:
        config = yaml.load(f.read(), Loader = yaml.FullLoader)

    logging.config.dictConfig(config['logging'])

    pkey = os.getenv("ACCOUNT_PRIVATE_KEY")
    polyscan_token = os.getenv("POLYSCAN_TOKEN")
    miner_bot = MinerBot(**config['bot'], pkey=pkey, polyscan_token=polyscan_token)
    miner_bot.run()

if __name__ == '__main__':
    main()