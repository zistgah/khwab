#ifndef CROWD_CINEMA_H
#define CROWD_CINEMA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CC_SHA256_SIZE 32U
#define CC_ZONE_COUNT 3U

typedef enum {
    CC_OK = 0,
    CC_INVALID_ARGUMENT = 1,
    CC_DUPLICATE_IDENTITY = 2,
    CC_OVERFLOW = 3,
    CC_NO_QUORUM = 4
} cc_status;

typedef struct {
    uint32_t voter_id;
    uint32_t candidate_id;
    uint32_t weight;
} cc_vote;

cc_status cc_authority_quorum(
    const uint32_t *authority_ids,
    const uint8_t *authorized,
    size_t count,
    size_t threshold,
    size_t *approved_count);

cc_status cc_vote_winner(
    const cc_vote *votes,
    size_t vote_count,
    uint32_t *winner_id,
    uint64_t *winner_weight);

cc_status cc_static_zone_mask(
    const uint8_t *activity_samples,
    size_t frame_count,
    uint8_t threshold,
    uint8_t *static_zone_mask);

cc_status cc_grayscale_frame_static_mask(
    const uint8_t *frames,
    size_t frame_count,
    size_t width,
    size_t height,
    uint8_t threshold,
    uint8_t *static_zone_mask);

void cc_sha256(const uint8_t *data, size_t length, uint8_t digest[CC_SHA256_SIZE]);

cc_status cc_frame_chain_append(
    const uint8_t previous_digest[CC_SHA256_SIZE],
    uint64_t pts,
    uint64_t duration,
    const uint8_t frame_digest[CC_SHA256_SIZE],
    uint8_t next_digest[CC_SHA256_SIZE]);

#ifdef __cplusplus
}
#endif

#endif
