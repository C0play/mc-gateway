from ..config.loader import load_config
from ..container.manager import ContainerManager
from ..container.repository import SQLContainerRepository
from ..host.manager import SSHHostManager
from ..host.repository import SQLHostRepository
from ..security.crypto import Crypto
from ..session.manager import SessionManager
from ..utils.composegen import ComposeGenerator
from ..utils.keygen import KeyGenerator
from ..utils.logger import logger
from ..whitelist.manager import WhitelistManager
from ..whitelist.repository import SQLWhitelistRepository
from .server import Server


def main():
    try:
        cfg = load_config()

        Crypto.initialize(cfg.storage.rcon_key)

        host_repo = SQLHostRepository()
        hosts = SSHHostManager(host_repo)

        container_repo = SQLContainerRepository(KeyGenerator())
        compose_gen =  ComposeGenerator(host_repo, container_repo)

        containers = ContainerManager(
            compose_gen,
            container_repo,
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

    except Exception as _:
        logger.critical("uncaught exception", exc_info=True)
        return 1


if __name__ == '__main__':
    main()
