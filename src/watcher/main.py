import sys
from .server import Server

def main():
    try:
        if len(sys.argv) > 1:
            return Server.send_cmd(sys.argv)
        else:
            srv = Server()
            srv.start()
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == '__main__':
    main()