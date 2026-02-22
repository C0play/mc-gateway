import argparse
import json
import socket

from ..utils.logger import logger


def _handle_error(full_cmd: dict, error_message: str):
    """
    Helper for printing error and logging it.

    Args:
        full_cmd: The command dictionary that caused the error.
        error_message: The error description.

    Returns:
        int: Always returns 1 (error exit code).
    """
    
    print(f"ERROR: {error_message}")
    logger.error(f"CLI ERROR: {full_cmd} -> {error_message}")
    return 1


def _print_response(data):
    """
    Universal response printer - just pretty prints JSON.

    Args:
        data: The data dictionary or string to print.
    """

    if isinstance(data, str):
        print(f"{data}")
    else:
        print(json.dumps(data, indent=3))



def send_request(port: int, command: str, kwargs: dict[str, str] = {}):
    """
    Encapsulates sending a command to the server socket and handling the response.

    Args:
        port: The port to connect to.
        command: The command name.
        kwargs: Dictionary of arguments for the command.
    
    Returns:
        int: 0 on success, 1 on failure.
    """

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

    # stop
    subparsers.add_parser("stop", help="Stop the server")

    # status
    subparsers.add_parser("status", help="Get server status")

    # list
    subparsers.add_parser("list", help="List all players, containers and hosts")

    # Player commands group
    player_parser = subparsers.add_parser("player", help="Player management")
    player_subparsers = player_parser.add_subparsers(dest="subcommand", required=True)

    # player add <name> <server_subdomain>
    parser_add_player = player_subparsers.add_parser("add", help="Add a player to whitelist")
    parser_add_player.add_argument("name", help="Player username")
    parser_add_player.add_argument("subdomain", help="Server subdomain")

    # player remove <name> <server_subdomain>
    parser_remove_player = player_subparsers.add_parser("remove", help="Remove a player from whitelist")
    parser_remove_player.add_argument("name", help="Player username")
    parser_remove_player.add_argument("subdomain", help="Server subdomain")

    # Container commands group
    container_parser = subparsers.add_parser("container", help="Container management")
    container_subparsers = container_parser.add_subparsers(dest="subcommand", required=True)

    # container add <ip> <port>
    parser_add_container = container_subparsers.add_parser("add", help="Add a container mapping")
    parser_add_container.add_argument("ip", help="Container IP address")
    parser_add_container.add_argument("port", type=int, help="Container port")

    # container remove <subdomain>
    parser_remove_container = container_subparsers.add_parser("remove", help="Remove a container mapping")
    parser_remove_container.add_argument("subdomain", help="Container subdomain")

    # container kickall <subdomain>
    parser_kickall_container = container_subparsers.add_parser("kickall", help="Kick all players connected to container")
    parser_kickall_container.add_argument("subdomain", help="Container subdomain")

    # Host commands group
    host_parser = subparsers.add_parser("host", help="Host management")
    host_subparsers = host_parser.add_subparsers(dest="subcommand", required=True)

    # host add <ip> <mac> <user> <path>
    parser_add_host = host_subparsers.add_parser("add", help="Add a physical host")
    parser_add_host.add_argument("ip", help="Host IP address")
    parser_add_host.add_argument("mac", help="Host MAC address")
    parser_add_host.add_argument("user", help="Host SSH user")
    parser_add_host.add_argument("path", help="Path on host")

    # host remove <ip>
    parser_remove_host = host_subparsers.add_parser("remove", help="Remove a physical host")
    parser_remove_host.add_argument("ip", help="Host IP address")
    
    # host kickall <ip>
    parser_kickall_host = host_subparsers.add_parser("kickall", help="Kick all players connected to host")
    parser_kickall_host.add_argument("ip", help="Host IP address")

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
    command_name = args.command

    if args.command == "player":
        if args.subcommand == "add":
            command_name = "add-player"
            socket_args = {
                "username": args.name,
                "subdomain": args.subdomain
            }
        elif args.subcommand == "remove":
            command_name = "remove-player"
            socket_args = {
                "username": args.name,
                "subdomain": args.subdomain
            }
            
    elif args.command == "container":
        if args.subcommand == "add":
            command_name = "add-container"
            socket_args = {
                "ip": args.ip,
                "port": str(args.port)
            }
        elif args.subcommand == "remove":
            command_name = "remove-container"
            socket_args = {
                "subdomain": args.subdomain
            }
        elif args.subcommand == "kickall":
            command_name = "kick-all"
            socket_args = {
                "subdomain": args.subdomain
            }
    elif args.command == "host":
        if args.subcommand == "add":
            command_name = "add-host"
            socket_args = {
                "ip": args.ip,
                "mac": args.mac,
                "user": args.user,
                "path": args.path
            }
        elif args.subcommand == "remove":
            command_name = "remove-host"
            socket_args = {
                "ip": args.ip
            }
        elif args.subcommand == "kickall":
            command_name = "kick-all"
            socket_args = {
                "ip": args.ip
            }
    
    return send_request(port, command_name, socket_args)