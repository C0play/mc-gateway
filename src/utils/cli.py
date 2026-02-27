import argparse
import json
import urllib.request
import urllib.error
import sys


def _handle_error(error_message: str):
    """
    Helper for printing error and logging it.

    Args:
        error_message: The error description.

    Returns:
        int: Always returns 1 (error exit code).
    """
    print(f"ERROR: {error_message}", file=sys.stderr)
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


def send_request(ip: str, port: int, method: str, endpoint: str, payload: dict  = {}):
    """
    Encapsulates sending an HTTP request to the server API.

    Args:
        ip: The IP to connect to.
        port: The port to connect to.
        method: HTTP method (GET, POST, DELETE).
        endpoint: API endpoint (e.g. "/status").
        payload: Dictionary of arguments for the command (body).
    
    Returns:
        int: 0 on success, 1 on failure.
    """
    url = f"http://{ip}:{port}{endpoint}"
    data = None
    headers = {"Content-Type": "application/json"}
    
    if payload:
        data = json.dumps(payload).encode("utf-8") 

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            if response.status != 200:
                return _handle_error(f"HTTP {response.status}: {response.reason}")
            
            if body := response.read().decode():
                try:
                    _print_response(json.loads(body))
                except json.JSONDecodeError:
                        print(body)
            else:
                print("OK")
            return 0

    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode()
            err_json = json.loads(err_body)
            detail = err_json.get("detail", str(e))
            
            if isinstance(detail, list):
                formatted_errors = []
                for err in detail:
                    if isinstance(err, dict):
                        loc = ".".join(str(l) for l in err.get("loc", []))
                        msg = err.get("msg", "Unknown error")
                        formatted_errors.append(f"- {loc}: {msg}")
                    else:
                        formatted_errors.append(f"- {str(err)}")
                
                if formatted_errors:
                    detail = "\n" + "\n".join(formatted_errors)
        except:
            detail = str(e)

        return _handle_error(f"Request failed: {detail}")
    
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, OSError) as e:
        return _handle_error(f"Server is not running or not accessible: {e}")
    except Exception as e:
        return _handle_error(str(e))



def send_cmd(argv: list[str]) -> int:
    
    parser = argparse.ArgumentParser(description="MC Gateway CLI")
    
    # Global arguments
    parser.add_argument("--ip", dest="req_ip", default="127.0.0.1", help="Gateway IP address (default: 127.0.0.1)")
    parser.add_argument("--port", dest="req_port", type=int, default=25566, help="Gateway control port (default: 25566)")

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # stop
    parser_stop = subparsers.add_parser("stop", help="Stop the server")
    parser_stop.set_defaults(
        func=lambda args: (
            "POST", "/stop", {}
    ))

    # status
    parser_status = subparsers.add_parser("status", help="Get server status")
    parser_status.set_defaults(
        func=lambda args: (
            "GET", "/status", {}
    ))

    # list
    list_parser = subparsers.add_parser("list", help="List all players, containers and hosts")
    list_parser.add_argument("-r", help="Resource to list", choices=("players", "containers", "hosts"), required=True)
    list_parser.set_defaults(
        func=lambda args: (
            "GET", f"/list/{args.r}", {}
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
            "POST", "/player/add",
            {"username": args.name, "subdomain": args.subdomain}
    ))

    # player remove <name> <server_subdomain>
    parser_remove_player = player_subparsers.add_parser("remove", help="Remove a player from whitelist")
    parser_remove_player.add_argument("name", help="Player username")
    parser_remove_player.add_argument("subdomain", help="Server subdomain")
    parser_remove_player.set_defaults(
        func=lambda args: (
            "DELETE", "/player/remove",
            {"username": args.name, "subdomain": args.subdomain}
    ))

    # Container commands group
    container_parser = subparsers.add_parser("container", help="Container management")
    container_subparsers = container_parser.add_subparsers(dest="subcommand", required=True)

    # container add <ip> <mc_port> <rcon_port>
    parser_add_container = container_subparsers.add_parser("add", help="Add a container mapping")
    parser_add_container.add_argument("ip", help="Container IP address")
    parser_add_container.add_argument("mc_port", type=int, help="Container Minecraft port")
    parser_add_container.add_argument("rcon_port", type=int, help="Container RCON port")
    parser_add_container.add_argument("--ram", dest="ram", type=str, help="Server memory")
    parser_add_container.add_argument("-v", dest="version", type=str, help="Game version")
    parser_add_container.add_argument(
        "-d",
        dest="difficulty",
        type=str,
        choices=("peaceful", "easy", "normal", "hard"),
        help="Game difficulty",
    )
    parser_add_container.add_argument("--viewd", dest="view_d", type=int, help="Game view distance")
    parser_add_container.add_argument(
        "--modr",
        dest="modr",
        choices=("release", "beta", "alpha"),
        help="Mod release type list"
    )
    parser_add_container.add_argument("--mods", dest="mods", nargs="+", help="Mod list")
    parser_add_container.set_defaults(
        func=lambda args: (
            "POST", "/container/add",
            {
                "ip": args.ip,
                "mc_port": args.mc_port,
                "rcon_port": args.rcon_port,
                "config": {k: v for k, v in {
                    "ram": args.ram,
                    "version": args.version,
                    "difficulty": args.difficulty,
                    "view_distance": args.view_d,
                    "modrinth_projects": args.mods,
                }.items() if v is not None}
            }
    ))

    # container remove <subdomain>
    parser_remove_container = container_subparsers.add_parser("remove", help="Remove a container mapping")
    parser_remove_container.add_argument("subdomain", help="Container subdomain")
    parser_remove_container.set_defaults(
        func=lambda args: (
            "DELETE", "/container/remove",
            {"subdomain": args.subdomain}
    ))

    # container kickall <subdomain>
    parser_kickall_container = container_subparsers.add_parser("kickall", help="Kick all players connected to container")
    parser_kickall_container.add_argument("subdomain", help="Container subdomain")
    parser_kickall_container.set_defaults(
        func=lambda args: (
            "POST", "/kick",
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
            "POST", "/host/add",
            {"ip": args.ip, "mac": args.mac, "user": args.user, "path": args.path}
    ))

    # host remove <ip>
    parser_remove_host = host_subparsers.add_parser("remove", help="Remove a physical host")
    parser_remove_host.add_argument("ip", help="Host IP address")
    parser_remove_host.set_defaults(
        func=lambda args: (
            "DELETE", "/host/remove",
            {"ip": args.ip}
    ))
    
    # host kickall <ip>
    parser_kickall_host = host_subparsers.add_parser("kickall", help="Kick all players connected to host")
    parser_kickall_host.add_argument("ip", help="Host IP address")
    parser_kickall_host.set_defaults(
        func=lambda args: (
            "POST", "/kick",
            {"ip": args.ip}
    ))

    # Parse arguments skipping argv[0] (script name)
    args = parser.parse_args(argv[1:])

    # Execute the handler function mapped to the command
    if hasattr(args, "func"):
        method, endpoint, payload = args.func(args)
        return send_request(args.req_ip, args.req_port, method, endpoint, payload)
    else:
        print(f"ERROR: No handler for command {args.command}")
        return 1



if __name__ == '__main__':
    send_cmd(sys.argv)