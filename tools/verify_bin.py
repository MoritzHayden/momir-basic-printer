#!/usr/bin/env python3
import struct
import uuid
import sys
import random
from pathlib import Path

# Resolve path relative to the repo root regardless of working directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_FILE = REPO_ROOT / "data" / "momir.bin"
MAX_CMC = 16

def read_exact(f, size):
    data = f.read(size)
    if len(data) != size:
        raise EOFError(f"Expected {size} bytes, got {len(data)}")
    return data

def verify():
    with open(BIN_FILE, "rb") as f:
        print("=== 1. Header Validation ===")
        # Header is 17 entries * 6 bytes = 102 bytes
        header_data = read_exact(f, (MAX_CMC + 1) * 6)
        cmc_directory = []
        
        total_cards = 0
        for cmc in range(MAX_CMC + 1):
            count, table_offset = struct.unpack_from("<HI", header_data, cmc * 6)
            cmc_directory.append((count, table_offset))
            total_cards += count
            print(f"CMC {cmc:2d}: {count:4d} cards (Offset Table at byte {table_offset})")
            
        print(f"\nTotal indexed creatures: {total_cards}")

        print("\n=== 2. Random O(1) Lookup Test ===")
        # Pick 3 random non-empty CMCs and read a random card from each
        test_cmcs = [cmc for cmc, (count, _) in enumerate(cmc_directory) if count > 0]
        selected_cmcs = random.sample(test_cmcs, min(3, len(test_cmcs)))

        for cmc in selected_cmcs:
            count, table_offset = cmc_directory[cmc]
            random_index = random.randint(0, count - 1)

            # Step 1: Seek to the offset pointer
            f.seek(table_offset + (random_index * 4))
            card_offset = struct.unpack("<I", read_exact(f, 4))[0]

            # Step 2: Seek to the packed card record
            f.seek(card_offset)
            record_len = struct.unpack("<H", read_exact(f, 2))[0]
            payload = read_exact(f, record_len)

            # Step 3: Unpack fields
            idx = 0
            card_uuid = uuid.UUID(bytes=payload[idx:idx+16])
            idx += 16

            name_len = payload[idx]
            idx += 1
            name = payload[idx:idx+name_len].decode("utf-8")
            idx += name_len

            mana_len = payload[idx]
            idx += 1
            mana = payload[idx:idx+mana_len].decode("utf-8")
            idx += mana_len

            type_len = payload[idx]
            idx += 1
            type_line = payload[idx:idx+type_len].decode("utf-8")
            idx += type_len

            pt_len = payload[idx]
            idx += 1
            pt = payload[idx:idx+pt_len].decode("utf-8")
            idx += pt_len

            oracle_len = struct.unpack_from("<H", payload, idx)[0]
            idx += 2
            oracle = payload[idx:idx+oracle_len].decode("utf-8")

            print(f"\n[CMC {cmc} | Index {random_index} | Offset {card_offset}]")
            print(f"Name:        {name} {mana}")
            print(f"Type:        {type_line}")
            print(f"P/T:         {pt if pt else 'N/A'}")
            print(f"Scryfall ID: {card_uuid}")
            print(f"Rules Text:\n{oracle}")
            print("-" * 50)

if __name__ == "__main__":
    verify()
