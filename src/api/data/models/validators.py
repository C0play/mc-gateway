from ....utils.keygen import KeyGenerator


def validate_subdomain(v: str) -> str:
    """Validates subdomain using KeyGenerator rules."""

    if KeyGenerator.validate(v):
        return v
    raise ValueError("Subdomain contains illegal characters")


def validate_ram_format(v: str) -> str:
    """Validates RAM allocation string (e.g., '2G', '4096M')."""

    size = v[-1]

    if size not in ["M", "G"]:
        raise ValueError("Choose from [M, G]")

    return v


def to_Mb(ram: str) -> int:
    return int(ram[:-1]) * (1024 if ram[-1] == "G" else 1)


def validate_init_min_max_consistency(init: str | None, max: str | None) -> None:
    """Ensures that min < max. Implicitely calls validate_ram_format() for all parameters."""

    if not (init and max):
        return

    validate_ram_format(init)
    validate_ram_format(max)

    init_amount = to_Mb(init)
    max_amount = to_Mb(max)

    if not (init_amount < max_amount):
        raise ValueError("RAM values have to satisfy the ordering: init < max")
