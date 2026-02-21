import argparse
import json
import socket

from ..utils.logger import logger


def _handle_error(full_cmd: dict, error_message: str):
    """Helper for printing error and logging it."""
    
    print(f"ERROR: {error_message}")
    logger.error(f"CLI ERROR: {full_cmd} -> {error_message}")
    return 1


def _print_response(data):
    """Universal response printer - just pretty prints JSON."""

    if isinstance(data, str):
        print(f"{data}")
    else:
        print(json.dumps(data, indent=3))



def send_request(port: int, command: str, kwargs: dict[str, str] = {}):
    """Encapsulates sending a command to the server socket and handling the response."""

    full_cmd = {
        "cmd_name": command,
        "kwargs": kwargs
    }
    
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3.0) as sock:
            logger.info(f"CLI send: {full_cmd}")
            sock.sendall(json.dumps(full_cmd).encode())

            response_data = sock.recv(4096).decode()
            if not response_data:
                return _handle_error(full_cmd, "Empty response from server")
            try:
                response = json.loads(response_data)
            except json.JSONDecodeError:
                return _handle_error(full_cmd, f"Invalid JSON response: {response_data}")

            if response.get("code") == "OK":
                _print_response(response.get("data"))
                logger.info(f"CLI OK: {full_cmd}")
                return 0
            else:
                return _handle_error(full_cmd, response.get('data', 'Unknown error'))

    except (ConnectionRefusedError, TimeoutError, OSError):
        return _handle_error(full_cmd, "server is not running or not accessible")
    except Exception as e:
        return _handle_error(full_cmd, str(e))



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
    
    socket_args = {}

    if args.command == "add-player":
        socket_args = {
            "username": args.name,
            "subdomain": args.subdomain
        }
    elif args.command == "remove-player":
        socket_args = {
            "username": args.name,
            "subdomain": args.subdomain
        }
    elif args.command == "add-container":
        socket_args = {
            "ip": args.ip,
            "port": str(args.port)
        }
    elif args.command == "remove-container":
        socket_args = {
            "subdomain": args.subdomain
        }
    elif args.command == "add-host":
        socket_args = {
            "ip": args.ip,
            "mac": args.mac,
            "user": args.user,
            "path": args.path
        }
    elif args.command == "remove-host":
        socket_args = {
            "ip": args.ip
        }
    elif args.command == "stop":
        pass
    elif args.command == "status":
        pass
    elif args.command == "list":
        pass

    return send_request(port, args.command, socket_args)