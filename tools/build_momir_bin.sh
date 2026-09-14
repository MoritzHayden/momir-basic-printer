#!/usr/bin/env bash
set -euo pipefail

# Resolve paths relative to the repo root regardless of working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_FILE="${REPO_ROOT}/data/momir.bin"
TEMP_FILE="${REPO_ROOT}/data/scryfall_oracle.jsonl"

echo "Checking dependencies..."
command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is required."; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "Error: curl is required."; exit 1; }

echo "Fetching Scryfall Oracle Cards bulk metadata..."

METADATA_JSON=$(curl -sS \
  -H "User-Agent: MomirBasic/1.0 (contact@momir.local)" \
  -H "Accept: application/json" \
  "https://api.scryfall.com/bulk-data/oracle-cards")

DOWNLOAD_URL=$(python3 -c "
import sys, json

try:
    data = json.loads('''$METADATA_JSON''')
except Exception as e:
    sys.stderr.write(f'Failed to parse metadata JSON: {e}\n')
    sys.exit(1)

if data.get('object') == 'error':
    sys.stderr.write(f'Scryfall API Error: {data.get(\"details\", data)}\n')
    sys.exit(1)

# Grab the JSONL URI, fallback to download_uri if present
url = data.get('jsonl_download_uri') or data.get('download_uri')
if not url:
    sys.stderr.write(f'No valid URI found. Keys: {list(data.keys())}\n')
    sys.exit(1)

print(url)
")

if [ -z "$DOWNLOAD_URL" ]; then
    echo "Failed to extract valid download URL."
    exit 1
fi

echo "Downloading Oracle Cards dataset..."
curl -L -H "User-Agent: MomirBasic/1.0 (contact@momir.local)" --progress-bar "$DOWNLOAD_URL" -o "$TEMP_FILE"

echo "Streaming JSONL, filtering creatures, and packing into $OUTPUT_FILE..."
python3 - "$TEMP_FILE" "$OUTPUT_FILE" << 'EOF'
import sys
import json
import struct
import uuid
import gzip

input_path = sys.argv[1]
output_path = sys.argv[2]

EXCLUDED_LAYOUTS = {
    'token', 'double_faced_token', 'emblem', 'art_series', 
    'vanguard', 'planar', 'scheme'
}

MAX_CMC = 16
cmc_buckets = [[] for _ in range(MAX_CMC + 1)]

def is_valid_creature(card):
    if card.get('layout') in EXCLUDED_LAYOUTS:
        return False
    if 'paper' not in card.get('games', []):
        return False

    if 'card_faces' in card:
        front_type = card['card_faces'][0].get('type_line', '').lower()
        return 'creature' in front_type
    
    type_line = card.get('type_line', '').lower()
    return 'creature' in type_line

# Open as gzip if compressed, otherwise plain text
def get_file_stream(path):
    with open(path, 'rb') as f:
        magic = f.read(2)
    if magic == b'\x1f\x8b':
        return gzip.open(path, 'rt', encoding='utf-8')
    return open(path, 'r', encoding='utf-8')

valid_count = 0
total_scanned = 0

with get_file_stream(input_path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        
        total_scanned += 1
        try:
            card = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not is_valid_creature(card):
            continue

        cmc_raw = card.get('cmc', -1)
        if cmc_raw != int(cmc_raw) or not (0 <= int(cmc_raw) <= MAX_CMC):
            continue

        cmc = int(cmc_raw)

        if 'card_faces' in card:
            front = card['card_faces'][0]
            name = front.get('name', card.get('name', ''))
            mana_cost = front.get('mana_cost', card.get('mana_cost', ''))
            type_line = front.get('type_line', '')
            power = front.get('power')
            toughness = front.get('toughness')
            pt = f"{power}/{toughness}" if power and toughness else ""
            oracle_text = front.get('oracle_text', '')
        else:
            name = card.get('name', '')
            mana_cost = card.get('mana_cost', '')
            type_line = card.get('type_line', '')
            power = card.get('power')
            toughness = card.get('toughness')
            pt = f"{power}/{toughness}" if power and toughness else ""
            oracle_text = card.get('oracle_text', '')

        raw_uuid = uuid.UUID(card['id']).bytes

        name_b = name.encode('utf-8')[:255]
        mana_b = mana_cost.encode('utf-8')[:255]
        type_b = type_line.encode('utf-8')[:255]
        pt_b = pt.encode('utf-8')[:255]
        oracle_b = oracle_text.encode('utf-8')[:65535]

        payload = (
            raw_uuid +
            struct.pack('<B', len(name_b)) + name_b +
            struct.pack('<B', len(mana_b)) + mana_b +
            struct.pack('<B', len(type_b)) + type_b +
            struct.pack('<B', len(pt_b)) + pt_b +
            struct.pack('<H', len(oracle_b)) + oracle_b
        )

        record = struct.pack('<H', len(payload)) + payload
        cmc_buckets[cmc].append(record)
        valid_count += 1

print(f"Total lines scanned: {total_scanned}")
print(f"Total valid creatures retained: {valid_count}")

HEADER_SIZE = (MAX_CMC + 1) * 6
TOTAL_RECORDS = valid_count
OFFSET_TABLES_SIZE = TOTAL_RECORDS * 4

data_start_offset = HEADER_SIZE + OFFSET_TABLES_SIZE

header_bytes = bytearray()
offset_tables_bytes = bytearray()
record_data_bytes = bytearray()

current_table_offset = HEADER_SIZE
current_record_offset = data_start_offset

for cmc in range(MAX_CMC + 1):
    cards_in_cmc = cmc_buckets[cmc]
    card_count = len(cards_in_cmc)

    header_bytes.extend(struct.pack('<HI', card_count, current_table_offset))
    current_table_offset += (card_count * 4)

    for record in cards_in_cmc:
        offset_tables_bytes.extend(struct.pack('<I', current_record_offset))
        record_data_bytes.extend(record)
        current_record_offset += len(record)

with open(output_path, 'wb') as f:
    f.write(header_bytes)
    f.write(offset_tables_bytes)
    f.write(record_data_bytes)

total_bytes = len(header_bytes) + len(offset_tables_bytes) + len(record_data_bytes)
print(f"Successfully generated {output_path} ({total_bytes} bytes)")
print("\nCMC Breakdown:")
for i in range(MAX_CMC + 1):
    print(f"  CMC {i:2d}: {len(cmc_buckets[i]):4d} creatures")
EOF

rm -f "$TEMP_FILE"
echo "Done. Final file created: $OUTPUT_FILE"
