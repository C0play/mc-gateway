import argparse
import json
import socket
import sys



def _handle_error(error_message: str):
    """
    Helper for printing error and logging it.

    Args:
        full_cmd: The command dictionary that caused the error.
        error_message: The error description.

    Returns:
        int: Always returns 1 (error exit code).
    """
    
    print(f"ERROR: {error_message}")
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



def send_request(ip: str, port: int, command: str, kwargs: dict[str, str] = {}):
    """
    Encapsulates sending a command to the server socket and handling the response.

    Args:
        ip: The IP to connect to.
        port: The port to connect to.
        command: The command name.
        kwargs: Dictionary of arguments for the command.
    
    Returns:
        int: 0 on success, 1 on failure.
    """

    full_cmd = {"cmd_name": command, "kwargs": kwargs }
    
    try:
        with socket.create_connection((ip, port), timeout=3.0) as sock:
            print(f"SEND: {full_cmd}")
            sock.sendall(json.dumps(full_cmd).encode())

            response_data = sock.recv(4096).decode()
            if not response_data:
                return _handle_error("Empty response from server")
            
            try:
                response = json.loads(response_data)
            except json.JSONDecodeError:
                return _handle_error(f"Invalid JSON response: {response_data}")

            if response.get("code") == "OK":
                _print_response(response.get("data"))
                print(f"OK: {full_cmd}")
                return 0
            else:
                return _handle_error(response.get('data', 'Unknown error'))

    except (ConnectionRefusedError, TimeoutError, OSError):
        return _handle_error("server is not running or not accessible")
    except Exception as e:
        return _handle_error(str(e))



def send_cmd(argv: list[str]) -> int:
    
    parser = argparse.ArgumentParser(description="MC Gateway CLI")
    
    # Global arguments
    parser.add_argument("--ip", dest="ip", default="127.0.0.1", help="Gateway IP address (default: 127.0.0.1)")
    parser.add_argument("--port", dest="port", type=int, default=25566, help="Gateway control port (default: 25566)")

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # stop
    parser_stop = subparsers.add_parser("stop", help="Stop the server")
    parser_stop.set_defaults(
        func=lambda args: (
            "stop", {}
    ))

    # status
    parser_status = subparsers.add_parser("status", help="Get server status")
    parser_status.set_defaults(
        func=lambda args: (
            "status", {}
    ))

    # list
    list_parser = subparsers.add_parser("list", help="List all players, containers and hosts")
    list_parser.add_argument("-r", help="Resource to list", choices=("players", "containers", "hosts"), required=True)
    list_parser.set_defaults(
        func=lambda args: (
            "list",
            {"resource": args.r}
    ))

    # Player commands group
    player_parser = subparsers.add_parser("player", help="Player management")
    player_subparsers = player_parser.add_subparsers(dest="subcommand", required=True)

    # player add <name> <server_subdomain>
    parser_add_player = player_subparsers.add_parser("add", help="Add a player to whitelist")
    parser_add_player.add_argument("name", help="Player username")
    parser_add_player.add_argument("subdomain", help="Server subdomain")
    parser_add_player.set_defaults(
        func=lambda args: (
            "add-player",
            {"username": args.name, "subdomain": args.subdomain}
    ))

    # player remove <name> <server_subdomain>
    parser_remove_player = player_subparsers.add_parser("remove", help="Remove a player from whitelist")
    parser_remove_player.add_argument("name", help="Player username")
    parser_remove_player.add_argument("subdomain", help="Server subdomain")
    parser_remove_player.set_defaults(
        func=lambda args: (
            "remove-player",
            {"username": args.name, "subdomain": args.subdomain}
    ))

    # Container commands group
    container_parser = subparsers.add_parser("container", help="Container management")
    container_subparsers = container_parser.add_subparsers(dest="subcommand", required=True)

    # container add <ip> <port>
    parser_add_container = container_subparsers.add_parser("add", help="Add a container mapping")
    parser_add_container.add_argument("ip", help="Container IP address")
    parser_add_container.add_argument("port", type=int, help="Container port")
    parser_add_container.set_defaults(
        func=lambda args: (
            "add-container",
            {"ip": args.ip, "port": str(args.port)}
    ))

    # container remove <subdomain>
    parser_remove_container = container_subparsers.add_parser("remove", help="Remove a container mapping")
    parser_remove_container.add_argument("subdomain", help="Container subdomain")
    parser_remove_container.set_defaults(
        func=lambda args: (
            "remove-container",
            {"subdomain": args.subdomain}
    ))

    # container kickall <subdomain>
    parser_kickall_container = container_subparsers.add_parser("kickall", help="Kick all players connected to container")
    parser_kickall_container.add_argument("subdomain", help="Container subdomain")
    parser_kickall_container.set_defaults(
        func=lambda args: (
            "kick-all",
            {"subdomain": args.subdomain}
    ))

    # Host commands group
    host_parser = subparsers.add_parser("host", help="Host management")
    host_subparsers = host_parser.add_subparsers(dest="subcommand", required=True)

    # host add <ip> <mac> <user> <path>
    parser_add_host = host_subparsers.add_parser("add", help="Add a physical host")
    parser_add_host.add_argument("ip", help="Host IP address")
    parser_add_host.add_argument("mac", help="Host MAC address")
    parser_add_host.add_argument("user", help="Host SSH user")
    parser_add_host.add_argument("path", help="Path on host")
    parser_add_host.set_defaults(
        func=lambda args: (
            "add-host",
            {"ip": args.ip, "mac": args.mac, "user": args.user, "path": args.path}
    ))

    # host remove <ip>
    parser_remove_host = host_subparsers.add_parser("remove", help="Remove a physical host")
    parser_remove_host.add_argument("ip", help="Host IP address")
    parser_remove_host.set_defaults(
        func=lambda args: (
            "remove-host",
            {"ip": args.ip}
    ))
    
    # host kickall <ip>
    parser_kickall_host = host_subparsers.add_parser("kickall", help="Kick all players connected to host")
    parser_kickall_host.add_argument("ip", help="Host IP address")
    parser_kickall_host.set_defaults(
        func=lambda args: (
            "kick-all",
            {"ip": args.ip}
    ))

    # Parse arguments skipping argv[0] (script name)
    args = parser.parse_args(argv[1:])

    # Execute the handler function mapped to the command
    if hasattr(args, "func"):
        command_name, socket_args = args.func(args)
        return send_request(args.ip, args.port, command_name, socket_args)
    else:
        print(f"ERROR: No handler for command {args.command}")
        return 1



if __name__ == '__main__':
    send_cmd(sys.argv)