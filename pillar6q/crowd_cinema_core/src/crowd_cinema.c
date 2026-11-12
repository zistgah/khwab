#include "crowd_cinema.h"

#include <limits.h>

cc_status cc_authority_quorum(
    const uint32_t *authority_ids,
    const uint8_t *authorized,
    size_t count,
    size_t threshold,
    size_t *approved_count)
{
    size_t approved = 0U;
    size_t index = 0U;
    size_t prior = 0U;

    if ((authority_ids == NULL) || (authorized == NULL) || (approved_count == NULL) ||
        (count == 0U) || (threshold == 0U) || (threshold > count)) {
        return CC_INVALID_ARGUMENT;
    }

    for (index = 0U; index < count; ++index) {
        if (authorized[index] > 1U) {
            return CC_INVALID_ARGUMENT;
        }
        if (authorized[index] == 1U) {
            for (prior = 0U; prior < index; ++prior) {
                if ((authorized[prior] == 1U) && (authority_ids[prior] == authority_ids[index])) {
                    return CC_DUPLICATE_IDENTITY;
                }
            }
            ++approved;
        }
    }
    *approved_count = approved;
    return (approved >= threshold) ? CC_OK : CC_NO_QUORUM;
}

cc_status cc_vote_winner(
    const cc_vote *votes,
    size_t vote_count,
    uint32_t *winner_id,
    uint64_t *winner_weight)
{
    size_t index = 0U;
    size_t prior = 0U;
    size_t candidate_index = 0U;
    uint64_t candidate_weight = 0U;
    uint64_t best_weight = 0U;
    uint32_t best_candidate = UINT32_MAX;
    int best_candidate_set = 0;

    if ((votes == NULL) || (vote_count == 0U) || (winner_id == NULL) ||
        (winner_weight == NULL)) {
        return CC_INVALID_ARGUMENT;
    }

    for (index = 0U; index < vote_count; ++index) {
        for (prior = 0U; prior < index; ++prior) {
            if (votes[prior].voter_id == votes[index].voter_id) {
                return CC_DUPLICATE_IDENTITY;
            }
        }
    }

    for (index = 0U; index < vote_count; ++index) {
        int candidate_seen = 0;
        for (prior = 0U; prior < index; ++prior) {
            if (votes[prior].candidate_id == votes[index].candidate_id) {
                candidate_seen = 1;
            }
        }
        if (candidate_seen != 0) {
            continue;
        }

        candidate_weight = 0U;
        for (candidate_index = index; candidate_index < vote_count; ++candidate_index) {
            if (votes[candidate_index].candidate_id == votes[index].candidate_id) {
                if (UINT64_MAX - candidate_weight < (uint64_t)votes[candidate_index].weight) {
                    return CC_OVERFLOW;
                }
                candidate_weight += (uint64_t)votes[candidate_index].weight;
            }
        }
        if ((best_candidate_set == 0) || (candidate_weight > best_weight) ||
            ((candidate_weight == best_weight) && (votes[index].candidate_id < best_candidate))) {
            best_weight = candidate_weight;
            best_candidate = votes[index].candidate_id;
            best_candidate_set = 1;
        }
    }

    *winner_id = best_candidate;
    *winner_weight = best_weight;
    return CC_OK;
}

cc_status cc_static_zone_mask(
    const uint8_t *activity_samples,
    size_t frame_count,
    uint8_t threshold,
    uint8_t *static_zone_mask)
{
    size_t frame = 0U;
    size_t zone = 0U;
    uint64_t total_delta = 0U;
    uint64_t comparisons = 0U;
    uint8_t left = 0U;
    uint8_t right = 0U;
    uint8_t mask = 0U;

    if ((activity_samples == NULL) || (static_zone_mask == NULL) || (frame_count < 2U)) {
        return CC_INVALID_ARGUMENT;
    }
    if (frame_count > (SIZE_MAX / (size_t)CC_ZONE_COUNT)) {
        return CC_OVERFLOW;
    }

    comparisons = (uint64_t)(frame_count - 1U);
    for (zone = 0U; zone < (size_t)CC_ZONE_COUNT; ++zone) {
        total_delta = 0U;
        for (frame = 1U; frame < frame_count; ++frame) {
            uint64_t delta = 0U;
            left = activity_samples[((frame - 1U) * (size_t)CC_ZONE_COUNT) + zone];
            right = activity_samples[(frame * (size_t)CC_ZONE_COUNT) + zone];
            delta = (left >= right) ? (uint64_t)(left - right) : (uint64_t)(right - left);
            if (UINT64_MAX - total_delta < delta) {
                return CC_OVERFLOW;
            }
            total_delta += delta;
        }
        if ((total_delta / comparisons) < (uint64_t)threshold) {
            mask = (uint8_t)(mask | (uint8_t)(1U << zone));
        }
    }
    *static_zone_mask = mask;
    return CC_OK;
}

cc_status cc_grayscale_frame_static_mask(
    const uint8_t *frames,
    size_t frame_count,
    size_t width,
    size_t height,
    uint8_t threshold,
    uint8_t *static_zone_mask)
{
    size_t frame_pixels = 0U;
    size_t frame = 0U;
    size_t zone = 0U;
    size_t row = 0U;
    size_t column = 0U;
    size_t zone_start = 0U;
    size_t zone_end = 0U;
    size_t previous_offset = 0U;
    size_t current_offset = 0U;
    uint64_t total_delta = 0U;
    uint64_t sample_count = 0U;
    uint64_t delta = 0U;
    uint8_t previous = 0U;
    uint8_t current = 0U;
    uint8_t mask = 0U;
    cc_status status = CC_OK;

    if ((frames == NULL) || (static_zone_mask == NULL) || (frame_count < 2U) ||
        (width == 0U) || (height < (size_t)CC_ZONE_COUNT)) {
        status = CC_INVALID_ARGUMENT;
    } else if (width > (SIZE_MAX / height)) {
        status = CC_OVERFLOW;
    } else {
        frame_pixels = width * height;
        if (frame_count > (SIZE_MAX / frame_pixels)) {
            status = CC_OVERFLOW;
        }
    }

    if (status == CC_OK) {
        for (zone = 0U; zone < (size_t)CC_ZONE_COUNT; ++zone) {
            zone_start = (zone * height) / (size_t)CC_ZONE_COUNT;
            zone_end = ((zone + 1U) * height) / (size_t)CC_ZONE_COUNT;
            total_delta = 0U;
            sample_count = 0U;
            for (frame = 1U; frame < frame_count; ++frame) {
                previous_offset = (frame - 1U) * frame_pixels;
                current_offset = frame * frame_pixels;
                for (row = zone_start; row < zone_end; ++row) {
                    for (column = 0U; column < width; ++column) {
                        previous = frames[previous_offset + (row * width) + column];
                        current = frames[current_offset + (row * width) + column];
                        delta = (previous >= current)
                            ? (uint64_t)(previous - current)
                            : (uint64_t)(current - previous);
                        if ((UINT64_MAX - total_delta < delta) ||
                            (sample_count == UINT64_MAX)) {
                            status = CC_OVERFLOW;
                            break;
                        }
                        total_delta += delta;
                        ++sample_count;
                    }
                    if (status != CC_OK) {
                        break;
                    }
                }
                if (status != CC_OK) {
                    break;
                }
            }
            if (status != CC_OK) {
                break;
            }
            if ((sample_count == 0U) ||
                ((total_delta / sample_count) < (uint64_t)threshold)) {
                mask = (uint8_t)(mask | (uint8_t)(1U << zone));
            }
        }
        if (status == CC_OK) {
            *static_zone_mask = mask;
        }
    }

    return status;
}
