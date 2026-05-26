"""Simple file encryption utilities using bit flip (XOR)."""


def bitflip_bytes(data: bytes) -> bytes:
    """XOR each byte with 0xFF to flip all bits."""
    return bytes(b ^ 0xFF for b in data)


def encrypt_file(input_path: str, output_path: str) -> None:
    """Encrypt a file using bit flip algorithm."""
    with open(input_path, 'rb') as f:
        data = f.read()
    with open(output_path, 'wb') as f:
        f.write(bitflip_bytes(data))


def decrypt_file(input_path: str, output_path: str) -> None:
    """Decrypt a file using bit flip algorithm."""
    encrypt_file(input_path, output_path)  # Same operation
