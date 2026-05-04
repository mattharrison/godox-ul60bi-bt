from __future__ import annotations

from godox_ul60bi_bt.crypto import (
    GODOX_CRC8_TABLE,
    aes_ccm_decrypt,
    aes_ccm_encrypt,
    k2,
    k3,
    k4,
    pack_proxy_config_pdu,
)


def test_godox_crc8_table_matches_apk() -> None:
    # Verified literals from com.godox.agm.CRC8Util.java
    # Index 7 is R.styleable... = 131
    # Index 8 is CipherSuite... = 194 (matching poly 0x8c LSB first)
    expected_start = [0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65]
    assert GODOX_CRC8_TABLE[:16] == expected_start
    assert len(GODOX_CRC8_TABLE) == 256


def test_k2_derivation() -> None:
    # Reference values from tasks.md and Telink implementation
    net_key = bytes.fromhex("125b33087af5d8f300114c2d4891378b")
    nid, enc_key, priv_key = k2(net_key)

    assert nid == 0x59
    assert enc_key.hex() == "459dece2bbfdc5a7e7e3ba3d172a5bcd"
    assert priv_key.hex() == "68a78e1bb5bca29dd926c3737af4b285"


def test_k3_derivation() -> None:
    # Reference value for NetKey 125b33087af5d8f300114c2d4891378b
    net_key = bytes.fromhex("125b33087af5d8f300114c2d4891378b")
    network_id = k3(net_key)
    assert network_id.hex() == "760552b77673d397"


def test_k4_derivation() -> None:
    # Reference value for AppKey 414bf26e7af1eb6a0f642628470ebf8d
    app_key = bytes.fromhex("414bf26e7af1eb6a0f642628470ebf8d")
    aid = k4(app_key)
    assert aid == 0x21


def test_aes_ccm_round_trip() -> None:
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    nonce = bytes.fromhex("00000000000000000000000000")  # 13 bytes
    plaintext = b"hello mesh"
    mic_length = 4

    ciphertext = aes_ccm_encrypt(key, nonce, plaintext, mic_length)
    assert len(ciphertext) == len(plaintext) + mic_length

    decrypted = aes_ccm_decrypt(key, nonce, ciphertext, mic_length)
    assert decrypted == plaintext


def test_pack_proxy_config_pdu_matches_expected_lengths() -> None:
    net_key = bytes.fromhex("bc6bf99f840f9ca379562468a110d2a9")
    filter_type_pdu = pack_proxy_config_pdu(
        opcode=0x00,
        parameters=b"\x01",
        net_key=net_key,
        iv_index=0,
        seq=300,
        src=0x0001,
    )
    whitelist_pdu = pack_proxy_config_pdu(
        opcode=0x01,
        parameters=b"\x00\x01\xff\xff",
        net_key=net_key,
        iv_index=0,
        seq=301,
        src=0x0001,
    )

    assert filter_type_pdu[0] == 0x02
    assert whitelist_pdu[0] == 0x02
    assert len(filter_type_pdu) == 20
    assert len(whitelist_pdu) == 23


def test_encrypt_decrypt_device_key_pdu_roundtrip() -> None:
    """Device key encrypt/decrypt is symmetric."""
    from godox_ul60bi_bt.crypto import decrypt_device_key_pdu, encrypt_device_key_pdu

    device_key = bytes.fromhex("6277be2be27af9818c3d79b62a2a8ae7")
    plaintext = bytes.fromhex("0880ff")  # Config CDG payload
    seq = 50000
    src = 0x0001
    dst = 0x0002
    iv_index = 0
    encrypted = encrypt_device_key_pdu(plaintext, device_key, iv_index, seq, src, dst)
    decrypted = decrypt_device_key_pdu(encrypted, device_key, iv_index, seq, src, dst)
    assert decrypted == plaintext


def test_encrypt_device_key_pdu_header_is_akf_zero() -> None:
    """Device key PDU header byte must have AKF=0 and AID=0, so header=0x00."""
    from godox_ul60bi_bt.crypto import encrypt_device_key_pdu

    device_key = bytes.fromhex("6277be2be27af9818c3d79b62a2a8ae7")
    encrypted = encrypt_device_key_pdu(b"\x00\x01\x02", device_key, 0, 1, 0x0001, 0x0002)
    # First byte is the transport header: AKF(1bit)|AID(6bits)|0(1bit)
    # AKF=0, AID=0 → 0x00
    assert encrypted[0] == 0x00


def test_encrypt_device_key_pdu_different_seq_produces_different_ciphertext() -> None:
    """Different sequence numbers must produce different ciphertexts (nonce includes SEQ)."""
    from godox_ul60bi_bt.crypto import encrypt_device_key_pdu

    device_key = bytes.fromhex("6277be2be27af9818c3d79b62a2a8ae7")
    plaintext = b"\x08\x80\xff"
    enc1 = encrypt_device_key_pdu(plaintext, device_key, 0, 100, 0x0001, 0x0002)
    enc2 = encrypt_device_key_pdu(plaintext, device_key, 0, 101, 0x0001, 0x0002)
    assert enc1 != enc2
