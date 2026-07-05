from __future__ import annotations

from Crypto.PublicKey import RSA


RSA_MODULUS = (
    "008aed7e057fe8f14c73550b0e6467b023616ddc8fa91846d2613cdb7f7621e3cada4cd5d812d627af6b87727ade4e26d26208b7326815941492b2204c3167ab2d53df1e3a2c9153bdb7c8c2e968df97a5e7e01cc410f92c4c2c2fba529b3ee988ebc1fca99ff5119e036d732c368acf8beba01aa2fdafa45b21e4de4928d0d403"
)
RSA_EXPONENT = "010001"


def raw_rsa_encrypt_hex(plain_text: str, modulus_hex: str = RSA_MODULUS, exponent_hex: str = RSA_EXPONENT) -> str:
    message_bytes = plain_text.encode("ascii")
    message_int = int.from_bytes(message_bytes, byteorder="big")
    modulus_int = int(modulus_hex, 16)
    exponent_int = int(exponent_hex, 16)

    # Construct through PyCryptodome so invalid key material fails early, then
    # use raw modular exponentiation to match the Kotlin implementation.
    key = RSA.construct((modulus_int, exponent_int))
    encrypted_int = pow(message_int, key.e, key.n)
    return f"{encrypted_int:0256x}"


def encrypt_password(password: str) -> str:
    return raw_rsa_encrypt_hex(password[::-1])
