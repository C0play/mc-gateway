from ..config.loader import load_config

from ..utils.logger import logger
from ..utils.keygen import KeyGenerator
from ..utils.crypto import CryptoProvider

from ..whitelist.manager import WhitelistManager
from ..whitelist.repository import SQLWhitelistRepository

from ..container.manager import ContainerManager
from ..container.repository import SQLContainerRepository

from ..host.manager import SSHHostManager
from ..host.repository import SQLHostRepository

from ..session.manager import SessionManager

from .server import Server



def main():
    try:
        cfg = load_config()

        CryptoProvider.initialize(cfg.storage.rcon_key)

        hosts = SSHHostManager(
            SQLHostRepository()
        )
        containers = ContainerManager(
            SQLContainerRepository(KeyGenerator()),
            hosts
        )
        whitelist = WhitelistManager(
            SQLWhitelistRepository()
        )
        sessions = SessionManager(
            containers,
            cfg.shutdown
        )
        
        Server(cfg, whitelist, sessions).start()

    except Exception as e:
        logger.critical("uncaught exception", exc_info=True)
        return 1


if __name__ == '__main__':
    main()