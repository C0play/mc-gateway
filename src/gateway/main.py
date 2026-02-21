import sys

from ..config.loader import load_config

from ..utils.logger import logger
from ..utils.keygen import KeyGenerator

from ..whitelist.manager import WhitelistManager
from ..whitelist.repository import WhitelistRepository

from ..container.manager import ContainerManager
from ..container.repository import SQLContainerRepository

from ..host.manager import SSHHostManager
from ..host.repository import HostRepository

from ..session.manager import SessionManager

from .server import Server
from .cli import send_cmd



def main():
    try:
        cfg = load_config()

        if len(sys.argv) > 1:
            return send_cmd(sys.argv, cfg.server.control_port)

        else:
            hosts = SSHHostManager(
                HostRepository()
            )

            containers = ContainerManager(
                SQLContainerRepository(KeyGenerator()),
                hosts
            )
            
            whitelist = WhitelistManager(
                WhitelistRepository()
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