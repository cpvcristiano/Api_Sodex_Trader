"""
EIP-712 signing for Sodex API.

Signing pipeline (from sodex-go-sdk-public/common/types/eip712.go):

1. Build ActionPayload: {"type": <actionName>, "params": <params>}
2. payloadHash = keccak256(compact JSON of ActionPayload)
3. ExchangeAction struct hash:
     structHash = keccak256(
         keccak256("ExchangeAction(bytes32 payloadHash,uint64 nonce)"),
         payloadHash,              # 32 bytes
         nonce as uint256,         # 32 bytes, uint64 in last 8 bytes
     )
4. EIP-712 final digest:
     digest = keccak256(0x19 || 0x01 || domainSeparator || structHash)
5. ECDSA-sign digest → 65 bytes (r || s || v) where v = 0 or 1
6. Wire format: 0x01 || 65-byte-sig  (total 66 bytes)
"""
import json

from eth_abi import encode
from eth_account import Account
from web3 import Web3


# EIP-712 domain type hash (standard)
_DOMAIN_TYPE_HASH = Web3.keccak(
    text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)

# ExchangeAction type hash (Sodex-specific)
_EXCHANGE_ACTION_TYPE_HASH = Web3.keccak(
    text="ExchangeAction(bytes32 payloadHash,uint64 nonce)"
)

_VERIFYING_CONTRACT = "0x0000000000000000000000000000000000000000"


def _domain_separator(domain_name: str, chain_id: int) -> bytes:
    """Compute the EIP-712 domain separator."""
    encoded = encode(
        ["bytes32", "bytes32", "bytes32", "uint256", "address"],
        [
            _DOMAIN_TYPE_HASH,
            Web3.keccak(text=domain_name),
            Web3.keccak(text="1"),
            chain_id,
            _VERIFYING_CONTRACT,
        ],
    )
    return Web3.keccak(encoded)


def _payload_hash(action_type: str, params: dict) -> bytes:
    """
    Compute keccak256 of the compact JSON ActionPayload.
    Field order: {"type": ..., "params": ...}
    """
    payload = {"type": action_type, "params": params}
    compact_json = json.dumps(payload, separators=(",", ":"))
    return Web3.keccak(text=compact_json)


def _exchange_action_struct_hash(payload_hash: bytes, nonce: int) -> bytes:
    """
    Compute EIP-712 struct hash for ExchangeAction{payloadHash, nonce}.

    structHash = keccak256(typeHash || payloadHash || nonce_as_uint256)

    nonce is encoded as 32 bytes big-endian (uint64 occupies last 8 bytes),
    matching Go's: binary.BigEndian.PutUint64(nonceBytes[24:], ea.Nonce)
    """
    # uint64 nonce → 32-byte word (left-padded with zeros)
    nonce_bytes = b"\x00" * 24 + nonce.to_bytes(8, "big")

    return Web3.keccak(
        bytes(_EXCHANGE_ACTION_TYPE_HASH) + bytes(payload_hash) + nonce_bytes
    )


def sign_action(
    private_key: str,
    domain_name: str,
    chain_id: int,
    action_type: str,
    params: dict,
    nonce: int,
) -> str:
    """
    Sign an API action and return the 66-byte wire-format signature as hex.

    Args:
        private_key:  Hex private key (with or without 0x prefix)
        domain_name:  "spot" for spot actions, "futures" for perps actions
        chain_id:     286623 for mainnet, 138565 for testnet
        action_type:  Action name (e.g. "newOrder", "cancelOrder")
        params:       Action parameters dict (fields in Go struct order)
        nonce:        Unix timestamp in milliseconds (same value sent in X-API-Nonce)

    Returns:
        Hex string: "0x01" + 65-byte ECDSA signature (r || s || v where v = 0 or 1)
    """
    # Step 1 — ActionPayload hash
    ph = _payload_hash(action_type, params)

    # Step 2 — ExchangeAction struct hash (includes nonce)
    struct_hash = _exchange_action_struct_hash(ph, nonce)

    # Step 3 — Domain separator
    domain_sep = _domain_separator(domain_name, chain_id)

    # Step 4 — EIP-712 final digest
    final_hash = Web3.keccak(b"\x19\x01" + bytes(domain_sep) + bytes(struct_hash))

    # Step 5 — ECDSA sign
    account = Account.from_key(private_key)
    signed = account.signHash(final_hash)

    # signed.signature = r(32) || s(32) || v(1), where v is 27 or 28 in eth_account
    # go-ethereum's crypto.SigToPub expects v = 0 or 1 (recovery id)
    sig_bytes = bytes(signed.signature)
    v = sig_bytes[-1]
    if v >= 27:
        v -= 27
    wire_sig = sig_bytes[:64] + bytes([v])  # r || s || v(0/1)

    # Step 6 — Prepend signature type byte 0x01 (EIP-712)
    return "0x01" + wire_sig.hex()
