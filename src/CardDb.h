#pragma once
#include <Arduino.h>
#include <LittleFS.h>

struct __attribute__((packed)) CmcHeaderEntry
{
    uint16_t card_count;
    uint32_t table_offset;
};

struct CardRecord
{
    uint8_t uuid[16];
    char name[64];
    char mana[32];
    char type_line[64];
    char pt[16];
    char oracle[1024];
};

class CardDb
{
private:
    uint8_t *buffer = nullptr;
    size_t buffer_size = 0;
    const CmcHeaderEntry *cmc_directory = nullptr;
    uint8_t _cmcSlots = 0; // number of CMC buckets in the binary (derived at load time)
    bool ready = false;

public:
    bool begin(const char *path = "/momir.bin")
    {
        if (!psramFound())
        {
            Serial.println("PSRAM not detected. Check build flags.");
            return false;
        }

        if (!LittleFS.begin(false))
        {
            Serial.println("LittleFS mount failed.");
            return false;
        }

        File file = LittleFS.open(path, "r");
        if (!file)
        {
            Serial.println("Failed to open binary dataset.");
            return false;
        }

        buffer_size = file.size();
        buffer = (uint8_t *)ps_malloc(buffer_size);
        if (!buffer)
        {
            Serial.printf("Failed to allocate %u bytes in PSRAM.\n", buffer_size);
            file.close();
            return false;
        }

        size_t bytes_read = file.read(buffer, buffer_size);
        file.close();

        if (bytes_read != buffer_size)
        {
            Serial.println("Incomplete file read into PSRAM.");
            free(buffer);
            buffer = nullptr;
            return false;
        }

        // Header directory starts at byte 0 of the buffer.
        cmc_directory = reinterpret_cast<const CmcHeaderEntry *>(buffer);

        // Derive the number of CMC slots from the first entry's table_offset.
        // The build script writes: table_offset[0] = HEADER_SIZE = cmcSlots * 6.
        // sizeof(CmcHeaderEntry) is 6 bytes (packed: uint16 + uint32).
        // This works for any MAX_CMC value the builder was compiled with.
        _cmcSlots = (uint8_t)(cmc_directory[0].table_offset / sizeof(CmcHeaderEntry));

        ready = true;
        Serial.printf("Database loaded to PSRAM: %u bytes. CMC slots: 0–%d\n",
                      buffer_size, _cmcSlots - 1);
        return true;
    }

    /**
     * Total number of CMC buckets in this binary (0 through getCmcSlots()-1).
     * Derived from the file header at load time — not a hardcoded constant.
     */
    uint8_t getCmcSlots() const { return _cmcSlots; }

    uint16_t getCount(uint8_t cmc) const
    {
        if (!ready || cmc >= _cmcSlots)
            return 0;
        return cmc_directory[cmc].card_count;
    }

    bool getRandomCard(uint8_t cmc, CardRecord &out_card) const
    {
        if (!ready || cmc >= _cmcSlots)
            return false;

        uint16_t count = cmc_directory[cmc].card_count;
        if (count == 0)
            return false;

        uint16_t rand_idx = random(0, count);

        // 1. Read record offset directly from the in-memory offset table
        uint32_t table_start = cmc_directory[cmc].table_offset;
        const uint32_t *offset_table = reinterpret_cast<const uint32_t *>(buffer + table_start);
        uint32_t card_addr = offset_table[rand_idx];

        if (card_addr >= buffer_size)
            return false;

        // 2. Point to the record payload
        const uint8_t *ptr = buffer + card_addr;
        uint16_t record_len = *reinterpret_cast<const uint16_t *>(ptr);
        ptr += 2;

        // 3. Extract UUID
        memcpy(out_card.uuid, ptr, 16);
        ptr += 16;

        // 4. Extract length-prefixed strings
        ptr = readPrefixedString(ptr, out_card.name, sizeof(out_card.name));
        ptr = readPrefixedString(ptr, out_card.mana, sizeof(out_card.mana));
        ptr = readPrefixedString(ptr, out_card.type_line, sizeof(out_card.type_line));
        ptr = readPrefixedString(ptr, out_card.pt, sizeof(out_card.pt));

        // 5. Extract 2-byte length-prefixed oracle rules text
        uint16_t oracle_len = *reinterpret_cast<const uint16_t *>(ptr);
        ptr += 2;
        size_t to_copy = min((size_t)oracle_len, sizeof(out_card.oracle) - 1);
        memcpy(out_card.oracle, ptr, to_copy);
        out_card.oracle[to_copy] = '\0';

        return true;
    }

private:
    const uint8_t *readPrefixedString(const uint8_t *src, char *dest, size_t max_len) const
    {
        uint8_t len = *src++;
        size_t to_copy = min((size_t)len, max_len - 1);
        memcpy(dest, src, to_copy);
        dest[to_copy] = '\0';
        return src + len;
    }
};

