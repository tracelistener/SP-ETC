/*
 * namb_reader.h — minimal C reader for the .namb binary model format.
 *
 * Enough of the format to feed the A2 engines: validate the container, confirm
 * the file describes the model shape the engine was generated for, and hand
 * back a pointer to the weights.
 *
 * What it deliberately does NOT do: build a model. The full loader
 * (nam::get_dsp_namb) constructs a NAMCore DSP object and pulls in
 * NeuralAmpModelerCore, Eigen and C++. The engine already *is* the model, so
 * all it needs from the file is the weight array and a shape check.
 *
 *   - C99, freestanding: <stdint.h>, <stddef.h>, <string.h>. No allocation, no
 *     C++, no exceptions, no filesystem.
 *   - Zero-copy: the weight pointer aims into your buffer, so a .namb in
 *     memory-mapped QSPI flash costs no RAM at all.
 *   - Format version 1, little-endian, as produced by the nam2namb tool.
 *
 * Format specification, reference loader and converter tools:
 *   https://github.com/tone-3000/nam-binary-loader
 *
 * Typical use:
 *
 *     namb_model_t m;
 *     if (namb_parse(flash_base, flash_len, &m) != NAMB_OK) { ... }
 *     if (namb_verify_crc(flash_base, flash_len) != NAMB_OK) { ... }
 *     if (namb_check_a2full(&m) != NAMB_OK) { ... }   (or namb_check_a2lite)
 *     nam_load_weights(m.weights, (int)m.weight_count);
 */
#ifndef NAMB_READER_H
#define NAMB_READER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
    NAMB_OK = 0,
    NAMB_ERR_SIZE,        /* buffer smaller than the fixed header + metadata   */
    NAMB_ERR_MAGIC,       /* not a .namb file                                  */
    NAMB_ERR_VERSION,     /* format version this reader does not know          */
    NAMB_ERR_TRUNCATED,   /* buffer shorter than the file claims to be         */
    NAMB_ERR_RANGE,       /* a block extends past the end of the file          */
    NAMB_ERR_ALIGN,       /* weights not 4-byte aligned in memory              */
    NAMB_ERR_CRC,         /* checksum mismatch — corrupt flash or bad transfer */
    NAMB_ERR_ARCH,        /* not a WaveNet model                               */
    NAMB_ERR_SHAPE        /* WaveNet, but not the shape this engine expects    */
} namb_status_t;

typedef struct
{
    /* Weights, pointing into your buffer. Valid as long as the buffer is. */
    const float* weights;
    uint32_t weight_count;

    /* From the metadata block. */
    double sample_rate;

    /* From the WaveNet config block — enough to identify the model shape. */
    uint8_t  in_channels;
    uint8_t  num_layer_arrays;
    uint16_t channels;          /* layer array 0 */
    uint16_t bottleneck;
    uint8_t  num_layers;        /* dilation count of layer array 0 */
    uint16_t head_kernel_size;
} namb_model_t;

/*
 * Validate the container and fill `out`. Cheap: fixed-size reads only, no scan
 * of the weight data. Does NOT check the CRC — call namb_verify_crc for that.
 */
namb_status_t namb_parse(const void* data, size_t size, namb_model_t* out);

/*
 * Verify the file's CRC32. O(file size): 8 KB for an A2-Lite capture, 49 KB
 * for A2-Full. Run it once at boot or after a flash write rather than on every
 * model switch. Worth doing on any data that came off flash, a filesystem, or
 * a wire.
 */
namb_status_t namb_verify_crc(const void* data, size_t size);

/*
 * Confirm the parsed model is the shape an engine was generated for: WaveNet,
 * 1 input channel, one layer array of 23 layers, head kernel 16, and
 *   A2-Lite: 3 channels / 3 bottleneck, 1,871 weights
 *   A2-Full: 8 channels / 8 bottleneck, 12,146 weights
 *
 * Any capture of that architecture passes; anything else is rejected before it
 * can be loaded into a mismatched engine.
 */
namb_status_t namb_check_a2lite(const namb_model_t* m);
namb_status_t namb_check_a2full(const namb_model_t* m);

/* Short human-readable form of a status code, for logging. */
const char* namb_status_str(namb_status_t s);

#ifdef __cplusplus
}
#endif

#endif /* NAMB_READER_H */
