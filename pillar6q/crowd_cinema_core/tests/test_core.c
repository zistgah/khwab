#include "crowd_cinema.h"

#include <stdio.h>
#include <string.h>

static int check(int condition, const char *name)
{
    if (condition == 0) {
        (void)fprintf(stderr, "FAIL: %s\n", name);
        return 1;
    }
    return 0;
}

int main(void)
{
    const uint32_t authorities[3] = {10U, 11U, 12U};
    const uint8_t authorized[3] = {1U, 0U, 1U};
    const uint32_t repeated_authorities[3] = {10U, 10U, 12U};
    const uint8_t repeated_authorized[3] = {1U, 1U, 1U};
    const cc_vote votes[4] = {
        {1U, 8U, 3U}, {2U, 4U, 4U}, {3U, 8U, 1U}, {4U, 4U, 0U}
    };
    const uint8_t activity[9] = {1U, 4U, 5U, 20U, 5U, 5U, 1U, 5U, 5U};
    const uint8_t grayscale_frames[18] = {
        10U, 10U, 10U, 20U, 20U, 20U, 30U, 30U, 30U,
        10U, 10U, 10U, 25U, 25U, 25U, 30U, 30U, 30U
    };
    const uint8_t empty_digest[CC_SHA256_SIZE] = {0U};
    const uint8_t frame_digest[CC_SHA256_SIZE] = {1U};
    const uint8_t expected_empty_sha[CC_SHA256_SIZE] = {
        0xe3U, 0xb0U, 0xc4U, 0x42U, 0x98U, 0xfcU, 0x1cU, 0x14U,
        0x9aU, 0xfbU, 0xf4U, 0xc8U, 0x99U, 0x6fU, 0xb9U, 0x24U,
        0x27U, 0xaeU, 0x41U, 0xe4U, 0x64U, 0x9bU, 0x93U, 0x4cU,
        0xa4U, 0x95U, 0x99U, 0x1bU, 0x78U, 0x52U, 0xb8U, 0x55U
    };
    const uint8_t abc[3] = {'a', 'b', 'c'};
    const uint8_t expected_abc_sha[CC_SHA256_SIZE] = {
        0xbaU, 0x78U, 0x16U, 0xbfU, 0x8fU, 0x01U, 0xcfU, 0xeaU,
        0x41U, 0x41U, 0x40U, 0xdeU, 0x5dU, 0xaeU, 0x22U, 0x23U,
        0xb0U, 0x03U, 0x61U, 0xa3U, 0x96U, 0x17U, 0x7aU, 0x9cU,
        0xb4U, 0x10U, 0xffU, 0x61U, 0xf2U, 0x00U, 0x15U, 0xadU
    };
    size_t approved = 0U;
    uint32_t winner = 0U;
    uint64_t winner_weight = 0U;
    uint8_t static_mask = 0U;
    uint8_t digest[CC_SHA256_SIZE];
    uint8_t chain[CC_SHA256_SIZE];
    int failures = 0;

    failures += check(cc_authority_quorum(authorities, authorized, 3U, 2U, &approved) == CC_OK,
        "quorum accepts two unique authorized authorities");
    failures += check(approved == 2U, "quorum reports exact count");
    failures += check(cc_authority_quorum(authorities, authorized, 3U, 3U, &approved) ==
        CC_NO_QUORUM, "quorum reports an unmet threshold");
    failures += check(cc_authority_quorum(repeated_authorities, repeated_authorized, 3U, 2U,
        &approved) == CC_DUPLICATE_IDENTITY, "quorum rejects repeated authority");
    failures += check(cc_vote_winner(votes, 4U, &winner, &winner_weight) == CC_OK,
        "vote tally succeeds");
    failures += check((winner == 4U) && (winner_weight == UINT64_C(4)),
        "vote tie resolves to lowest candidate ID");
    failures += check(cc_static_zone_mask(activity, 3U, 1U, &static_mask) == CC_OK,
        "zone activity analysis succeeds");
    failures += check(static_mask == UINT8_C(6), "static midground and background are detected");
    failures += check(cc_grayscale_frame_static_mask(grayscale_frames, 2U, 3U, 3U, 3U,
        &static_mask) == CC_OK, "grayscale frame liveness analysis succeeds");
    failures += check(static_mask == UINT8_C(5),
        "pixel differences detect static upper and lower image zones");
    failures += check(cc_grayscale_frame_static_mask(grayscale_frames, 2U, 3U, 2U, 3U,
        &static_mask) == CC_INVALID_ARGUMENT, "pixel analyzer rejects insufficient zone height");
    cc_sha256(NULL, 0U, digest);
    failures += check(memcmp(digest, expected_empty_sha, CC_SHA256_SIZE) == 0,
        "SHA-256 matches the empty-message test vector");
    cc_sha256(abc, sizeof(abc), digest);
    failures += check(memcmp(digest, expected_abc_sha, CC_SHA256_SIZE) == 0,
        "SHA-256 matches the abc test vector");
    failures += check(cc_frame_chain_append(empty_digest, UINT64_C(0), UINT64_C(40),
        frame_digest, chain) == CC_OK, "frame-chain append succeeds");
    failures += check(memcmp(chain, empty_digest, CC_SHA256_SIZE) != 0,
        "frame-chain append changes the chain digest");

    if (failures != 0) {
        return 1;
    }
    (void)puts("All C11 core checks passed.");
    return 0;
}
