/*
 * namb_reader.c — see namb_reader.h.
 *
 * Format version 1 layout (all little-endian):
 *
 *   file header, 32 bytes @ 0
 *     0  u32  magic 'NAMB' (0x4E414D42)
 *     4  u16  format version
 *     6  u16  flags (reserved)
 *     8  u32  total file size
 *    12  u32  weights offset
 *    16  u32  total weight count
 *    20  u32  model block size
 *    24  u32  CRC32, computed over the file with these 4 bytes skipped
 *    28  u32  reserved
 *
 *   metadata block, 48 bytes @ 32
 *     0  u8[3]  config version major/minor/patch
 *     3  u8     metadata flags
 *     4  f64    sample rate
 *    12  f64    loudness
 *    20  f64    input level
 *    28  f64    output level
 *    36  u8[12] reserved
 *
 *   model block @ 80
 *     0  u8   architecture id (3 = WaveNet)
 *     1  u8   reserved
 *     2  u16  config size
 *     4  ...  architecture config
 *
 *   WaveNet config
 *     0  u8   in_channels
 *     1  u8   has_head
 *     2  u8   num_layer_arrays
 *     3  u8   has_condition_dsp
 *     4  ...  [condition DSP block if has_condition_dsp]
 *     ...     per layer array: input_size u16, condition_size u16,
 *             head_size u16, channels u16, bottleneck u16,
 *             head_kernel_size u16, head_bias u8, num_dilations u8,
 *             groups_input u16, groups_input_mixin u16,
 *             layer1x1 (4 B), head1x1 (6 B), 8 x FiLM params (4 B each),
 *             dilations [n x i32], kernel_sizes [n x u16], ...
 *
 *   weights @ weights_offset: weight_count x f32, 4-byte aligned
 *
 * Everything is byte-packed — no implicit padding between fields — so all reads
 * go through memcpy rather than casts, which also keeps this correct on targets
 * that fault on unaligned access.
 */
#include "namb_reader.h"

#include <string.h>

#define NAMB_MAGIC            0x4E414D42u
#define NAMB_FORMAT_VERSION   1u
#define NAMB_HEADER_SIZE      32u
#define NAMB_METADATA_SIZE    48u
#define NAMB_MODEL_BLOCK_OFF  (NAMB_HEADER_SIZE + NAMB_METADATA_SIZE)  /* 80 */
#define NAMB_ARCH_WAVENET     3u

/* Shape of the A2 architecture, shared by A2-Lite and A2-Full. */
#define A2_EXPECT_IN_CHANNELS   1
#define A2_EXPECT_LAYER_ARRAYS  1
#define A2_EXPECT_LAYERS        23
#define A2_EXPECT_HEAD_KS       16

/* --- byte-packed little-endian reads ------------------------------------- */

static uint16_t rd_u16(const uint8_t* p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t rd_u32(const uint8_t* p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static double rd_f64(const uint8_t* p)
{
    /* The format stores IEEE 754 doubles in little-endian byte order. On a
       little-endian target (every ARM configuration in practice) this is a
       straight copy. */
    double v;
    memcpy(&v, p, sizeof(v));
    return v;
}

/* --- CRC32, IEEE 802.3, bitwise (no 1 KB table on a small target) -------- */

static uint32_t crc32_byte(uint32_t crc, uint8_t b)
{
    uint32_t c = (crc ^ b) & 0xFFu;
    for (int i = 0; i < 8; i++)
        c = (c & 1u) ? ((c >> 1) ^ 0xEDB88320u) : (c >> 1);
    return c ^ (crc >> 8);
}

/* --- public -------------------------------------------------------------- */

namb_status_t namb_parse(const void* data, size_t size, namb_model_t* out)
{
    const uint8_t* d = (const uint8_t*)data;

    if (!d || !out || size < NAMB_MODEL_BLOCK_OFF)
        return NAMB_ERR_SIZE;

    if (rd_u32(d + 0) != NAMB_MAGIC)
        return NAMB_ERR_MAGIC;
    if (rd_u16(d + 4) != NAMB_FORMAT_VERSION)
        return NAMB_ERR_VERSION;

    uint32_t total_size   = rd_u32(d + 8);
    uint32_t weights_off  = rd_u32(d + 12);
    uint32_t weight_count = rd_u32(d + 16);

    if (total_size < NAMB_MODEL_BLOCK_OFF || (size_t)total_size > size)
        return NAMB_ERR_TRUNCATED;

    /* Weight section must lie inside the file; guard the multiply too. */
    if (weights_off > total_size || weight_count > (0xFFFFFFFFu / 4u))
        return NAMB_ERR_RANGE;
    if (weights_off + weight_count * 4u > total_size)
        return NAMB_ERR_RANGE;

    /* We hand out a float* into the caller's buffer, so it must be aligned. A
       .namb keeps weights at a 4-byte offset, which means this only trips when
       the buffer itself is misaligned — easy to fix, hard to debug otherwise. */
    if (((uintptr_t)(d + weights_off) & 3u) != 0u)
        return NAMB_ERR_ALIGN;

    memset(out, 0, sizeof(*out));
    out->weights      = (const float*)(const void*)(d + weights_off);
    out->weight_count = weight_count;
    out->sample_rate  = rd_f64(d + NAMB_HEADER_SIZE + 4);

    /* Model block. */
    const uint8_t* mb = d + NAMB_MODEL_BLOCK_OFF;
    if ((size_t)(NAMB_MODEL_BLOCK_OFF + 4u) > total_size)
        return NAMB_ERR_RANGE;
    if (mb[0] != NAMB_ARCH_WAVENET)
        return NAMB_ERR_ARCH;

    /* WaveNet config. */
    const uint8_t* wn = mb + 4;
    if ((size_t)(wn - d) + 4u > total_size)
        return NAMB_ERR_RANGE;

    out->in_channels      = wn[0];
    out->num_layer_arrays = wn[2];

    /*
     * A recursive condition DSP would sit between here and the layer arrays,
     * and skipping it means parsing a whole nested model. The A2 shape has
     * none, and this engine could not run one anyway, so reject it rather than
     * silently misreading the fields that follow.
     */
    if (wn[3] != 0u)
        return NAMB_ERR_SHAPE;
    if (out->num_layer_arrays < 1u)
        return NAMB_ERR_SHAPE;

    /* Layer array 0 — the only one an A2 model has. */
    const uint8_t* la = wn + 4;
    if ((size_t)(la - d) + 18u > total_size)
        return NAMB_ERR_RANGE;

    out->channels         = rd_u16(la + 6);
    out->bottleneck       = rd_u16(la + 8);
    out->head_kernel_size = rd_u16(la + 10);
    out->num_layers       = la[13];   /* num_dilations */

    return NAMB_OK;
}

namb_status_t namb_verify_crc(const void* data, size_t size)
{
    const uint8_t* d = (const uint8_t*)data;

    if (!d || size < NAMB_HEADER_SIZE)
        return NAMB_ERR_SIZE;

    uint32_t total_size = rd_u32(d + 8);
    uint32_t stored     = rd_u32(d + 24);

    if (total_size < NAMB_HEADER_SIZE || (size_t)total_size > size)
        return NAMB_ERR_TRUNCATED;

    uint32_t crc = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < total_size; i++)
    {
        if (i >= 24u && i < 28u)
            continue;            /* the checksum field itself */
        crc = crc32_byte(crc, d[i]);
    }
    crc ^= 0xFFFFFFFFu;

    return (crc == stored) ? NAMB_OK : NAMB_ERR_CRC;
}

static namb_status_t check_a2(const namb_model_t* m, uint16_t channels, uint32_t weights)
{
    if (!m)
        return NAMB_ERR_SIZE;
    if (m->weight_count != weights)
        return NAMB_ERR_SHAPE;
    if (m->in_channels != A2_EXPECT_IN_CHANNELS)
        return NAMB_ERR_SHAPE;
    if (m->num_layer_arrays != A2_EXPECT_LAYER_ARRAYS)
        return NAMB_ERR_SHAPE;
    if (m->channels != channels)
        return NAMB_ERR_SHAPE;
    if (m->bottleneck != channels)
        return NAMB_ERR_SHAPE;
    if (m->num_layers != A2_EXPECT_LAYERS)
        return NAMB_ERR_SHAPE;
    if (m->head_kernel_size != A2_EXPECT_HEAD_KS)
        return NAMB_ERR_SHAPE;
    return NAMB_OK;
}

namb_status_t namb_check_a2lite(const namb_model_t* m)
{
    return check_a2(m, 3, 1871);
}

namb_status_t namb_check_a2full(const namb_model_t* m)
{
    return check_a2(m, 8, 12146);
}

const char* namb_status_str(namb_status_t s)
{
    switch (s)
    {
        case NAMB_OK:            return "ok";
        case NAMB_ERR_SIZE:      return "buffer too small";
        case NAMB_ERR_MAGIC:     return "not a .namb file";
        case NAMB_ERR_VERSION:   return "unsupported .namb format version";
        case NAMB_ERR_TRUNCATED: return "file truncated";
        case NAMB_ERR_RANGE:     return "block extends past end of file";
        case NAMB_ERR_ALIGN:     return "weights not 4-byte aligned";
        case NAMB_ERR_CRC:       return "checksum mismatch";
        case NAMB_ERR_ARCH:      return "not a WaveNet model";
        case NAMB_ERR_SHAPE:     return "wrong model shape for this engine";
        default:                 return "unknown error";
    }
}
