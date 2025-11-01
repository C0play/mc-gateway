import sys
from .server import Server
from ..logger.logger import logger

def main():
    try:
        if len(sys.argv) > 1:
            return Server.send_cmd(sys.argv)
        else:
            srv = Server()
            srv.start()
    except Exception as e:
        logger.critical("uncaught exception", exc_info=True)
        return 1

if __name__ == '__main__':
    main()