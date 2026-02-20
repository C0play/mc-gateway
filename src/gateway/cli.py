import argparse
import json
import socket
import sys

from ..utils.logger import logger


def send_request(port: int, command: str, args: list[str] | None = None):
    """Encapsulates sending a command to the server socket and handling the response."""
    full_cmd = f"{command} {' '.join(args) if args else ''}".strip()
    
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3.0) as s:
            logger.info(f"CLI send: {full_cmd}")
            s.sendall(full_cmd.encode())

            response_data = s.recv(4096).decode()
            if not response_data:
                err = "ERROR: Empty response from server"
                print(err)
                logger.error(f"CLI ERROR: {full_cmd} -> {err}")
                return 1

            try:
                response = json.loads(response_data)
            except json.JSONDecodeError:
                err = f"ERROR: Invalid JSON response: {response_data}"
                print(err)
                logger.error(f"CLI ERROR: {full_cmd} -> {err}")
                return 1

            if response.get("status") == "OK":
                if "message" in response:
                    print(f"SUCCESS: {response['message']}")
                if "clients" in response:
                    print(f"Clients: {response['clients']}")
                if "players" in response:
                    print("Whitelist:")
                    players = response.get("players", {})
                    if isinstance(players, dict):
                         for username, info in players.items():
                            subs = info.get('subdomains') if isinstance(info, dict) else None
                            if subs:
                                print(f"  {username}: {', '.join(subs)}")
                if "containers" in response:
                    print("Containers:")
                    containers = response.get("containers", {})
                    if isinstance(containers, dict):
                         for subdomain, info in containers.items():
                              print(f"  {subdomain}: {info.get('ip')}:{info.get('port')}")
                if "hosts" in response:
                    print("Hosts:")
                    hosts = response.get("hosts", {})
                    if isinstance(hosts, dict):
                        for ip, info in hosts.items():
                            print(f"  {ip}: {info.get('mac')}, {info.get('user')}, {info.get('path')}")

                logger.info(f"CLI OK: {full_cmd}")
                return 0
            else:
                err = f"ERROR: {response.get('message', 'Unknown error')}"
                print(err)
                logger.error(f"CLI ERROR: {full_cmd} -> {err}")
                return 1

    except (ConnectionRefusedError, TimeoutError, OSError):
        err = "ERROR: server is not running or not accessible"
        print(err)
        logger.error(f"CLI ERROR: {full_cmd} -> {err}")
        return 1
    except Exception as e:
        err = f"ERROR: {e}"
        print(err)
        logger.error(f"CLI ERROR: {full_cmd} -> {e}")
        return 1


def send_cmd(argv: list[str], port: int) -> int:
    parser = argparse.ArgumentParser(description="MC Gateway CLI")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --stop
    subparsers.add_parser("stop", help="Stop the server")

    # --status
    subparsers.add_parser("status", help="Get server status")

    # --list
    subparsers.add_parser("list", help="List all players, containers and hosts")

    # --add-player <name> <server_subdomain>
    parser_add_player = subparsers.add_parser("add-player", help="Add a player to whitelist")
    parser_add_player.add_argument("name", help="Player username")
    parser_add_player.add_argument("subdomain", help="Server subdomain")

    # --remove-player <name> <server_subdomain>
    parser_remove_player = subparsers.add_parser("remove-player", help="Remove a player from whitelist")
    parser_remove_player.add_argument("name", help="Player username")
    parser_remove_player.add_argument("subdomain", help="Server subdomain")

    # --add-container <ip> <port>
    parser_add_container = subparsers.add_parser("add-container", help="Add a container mapping")
    parser_add_container.add_argument("ip", help="Container IP address")
    parser_add_container.add_argument("port", type=int, help="Container port")

    # --remove-container <subdomain>
    parser_remove_container = subparsers.add_parser("remove-container", help="Remove a container mapping")
    parser_remove_container.add_argument("subdomain", help="Container subdomain")

    # --add-host <ip> <mac> <user> <path>
    parser_add_host = subparsers.add_parser("add-host", help="Add a physical host")
    parser_add_host.add_argument("ip", help="Host IP address")
    parser_add_host.add_argument("mac", help="Host MAC address")
    parser_add_host.add_argument("user", help="Host SSH user")
    parser_add_host.add_argument("path", help="Path on host")

    # --remove-host <ip>
    parser_remove_host = subparsers.add_parser("remove-host", help="Remove a physical host")
    parser_remove_host.add_argument("ip", help="Host IP address")

    # Parse arguments skipping argv[0] (script name)
    try:
        
        # Clean up input args to match subparser names (remove leading -- if present for command)
        clean_args = []
        if len(argv) > 1:
            cmd = argv[1].lstrip('-')
            clean_args = [cmd] + argv[2:]
        else:
             # This will trigger print_help() because command is required
             clean_args = []

        args = parser.parse_args(clean_args)
    except SystemExit:
        # Argparse calls sys.exit() on error or --help, we want to return from function instead
        return 1

    # Map argparse result to the command string expected by the server socket
    
    socket_cmd = f"{args.command}"
    socket_args = []

    if args.command == "add-player":
        socket_args = [args.name, args.subdomain]
    elif args.command == "remove-player":
        socket_args = [args.name, args.subdomain]
    elif args.command == "add-container":
        socket_args = [args.ip, str(args.port)]
    elif args.command == "remove-container":
        socket_args = [args.subdomain]
    elif args.command == "add-host":
        socket_args = [args.ip, args.mac, args.user, args.path]
    elif args.command == "remove-host":
        socket_args = [args.ip]
    elif args.command == "stop":
        pass
    elif args.command == "status":
        pass
    elif args.command == "list":
        pass

    return send_request(port, socket_cmd, socket_args)
