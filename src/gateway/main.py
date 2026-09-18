from ..config.loader import load_config
from ..container.manager import ControllerContainerManager
from ..container.repository import SQLContainerRepository
from ..host.manager import ControllerHostManager
from ..host.repository import SQLHostRepository
from ..session.manager import SessionManager
from ..utils.keygen import KeyGenerator
from ..utils.logger import logger
from ..whitelist.manager import WhitelistManager
from ..whitelist.repository import SQLWhitelistRepository
from .server import Server


def main():
    try:
        cfg = load_config()

        host_repo = SQLHostRepository()
        hosts = ControllerHostManager(host_repo)

        container_repo = SQLContainerRepository(KeyGenerator())

        containers = ControllerContainerManager(
            container_repo,
            hosts,
        )

        whitelist = WhitelistManager(SQLWhitelistRepository())

        sessions = SessionManager(containers, cfg.shutdown)

        Server(cfg, whitelist, sessions).start()

    except Exception as _:
        logger.critical("uncaught exception", exc_info=True)
        return 1


if __name__ == "__main__":
    main()
