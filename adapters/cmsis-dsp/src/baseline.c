/* SPDX-License-Identifier: MIT OR Apache-2.0 */
#include "dsp/filtering_functions.h"
#include <stddef.h>
void verify_raw_stream(const float *coeff, uint16_t taps, float *state,
                       const float *input, float *output, uint32_t block, uint32_t blocks) {
    arm_fir_instance_f32 s;
    arm_fir_init_f32(&s, taps, coeff, state, block);
    for (uint32_t i = 0; i < blocks; ++i)
        arm_fir_f32(&s, input + (size_t)i * block, output + (size_t)i * block, block);
}
size_t verify_instance_size(void) { return sizeof(arm_fir_instance_f32); }
size_t verify_state_offset(void) { return offsetof(arm_fir_instance_f32, pState); }
size_t verify_coeff_offset(void) { return offsetof(arm_fir_instance_f32, pCoeffs); }
