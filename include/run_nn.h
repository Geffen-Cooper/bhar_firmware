/*
 * SPDX-FileCopyrightText: Copyright 2024 Arm Limited and/or its affiliates <open-source-office@arm.com>
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the License); you may
 * not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <arm_nnfunctions.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

#include "NN/test_data.h"

// define the test to run
#define LSTM_TEST
// #define FC_TEST


#ifdef LSTM_TEST

// update the buffer size if adding a unit test with larger buffer.
#define LARGEST_BUFFER_SIZE LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE *LSTM_ONE_TIME_STEP_BHAR_BATCH_SIZE *LSTM_ONE_TIME_STEP_BHAR_TIME_STEPS

int8_t buffer1[LARGEST_BUFFER_SIZE];
int8_t buffer2[LARGEST_BUFFER_SIZE];
int8_t buffer3[LARGEST_BUFFER_SIZE];


void LSTM_ONE_TIME_STEP_BHAR(void)
{
    int8_t output[LSTM_ONE_TIME_STEP_BHAR_BATCH_SIZE * LSTM_ONE_TIME_STEP_BHAR_TIME_STEPS * LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE] = {0};
    const arm_cmsis_nn_status expected = ARM_CMSIS_NN_SUCCESS;
    const int8_t *output_ref = &lstm_one_time_step_bhar_output[0];
    const int32_t output_ref_size =
        LSTM_ONE_TIME_STEP_BHAR_BATCH_SIZE * LSTM_ONE_TIME_STEP_BHAR_TIME_STEPS * LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE;

    int32_t input_data_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];
    int32_t forget_data_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];
    int32_t cell_data_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];
    int32_t output_data_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];

    int32_t input_hidden_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];
    int32_t forget_hidden_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];
    int32_t cell_hidden_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];
    int32_t output_hidden_kernel_sum[LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE];

    arm_vector_sum_s8(&input_data_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_input_gate_input_weights[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_ZERO_POINT,
                      0,
                      &lstm_one_time_step_bhar_input_gate_bias[0]);
    arm_vector_sum_s8(&forget_data_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_forget_gate_input_weights[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_ZERO_POINT,
                      0,
                      &lstm_one_time_step_bhar_forget_gate_bias[0]);
    arm_vector_sum_s8(&cell_data_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_cell_gate_input_weights[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_ZERO_POINT,
                      0,
                      &lstm_one_time_step_bhar_cell_gate_bias[0]);
    arm_vector_sum_s8(&output_data_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_output_gate_input_weights[0],
                      LSTM_ONE_TIME_STEP_BHAR_INPUT_ZERO_POINT,
                      0,
                      &lstm_one_time_step_bhar_output_gate_bias[0]);

    arm_vector_sum_s8(&input_hidden_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_input_gate_hidden_weights[0],
                      -LSTM_ONE_TIME_STEP_BHAR_OUTPUT_ZERO_POINT,
                      0,
                      NULL);
    arm_vector_sum_s8(&forget_hidden_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_forget_gate_hidden_weights[0],
                      -LSTM_ONE_TIME_STEP_BHAR_OUTPUT_ZERO_POINT,
                      0,
                      NULL);
    arm_vector_sum_s8(&cell_hidden_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_cell_gate_hidden_weights[0],
                      -LSTM_ONE_TIME_STEP_BHAR_OUTPUT_ZERO_POINT,
                      0,
                      NULL);
    arm_vector_sum_s8(&output_hidden_kernel_sum[0],
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                      &lstm_one_time_step_bhar_output_gate_hidden_weights[0],
                      -LSTM_ONE_TIME_STEP_BHAR_OUTPUT_ZERO_POINT,
                      0,
                      NULL);
    
    // INPUT GATE
    const cmsis_nn_lstm_gate gate_input = {LSTM_ONE_TIME_STEP_BHAR_INPUT_GATE_INPUT_MULTIPLIER,
                                           LSTM_ONE_TIME_STEP_BHAR_INPUT_GATE_INPUT_SHIFT,
                                           &lstm_one_time_step_bhar_input_gate_input_weights[0],
                                           &input_data_kernel_sum[0],
                                           LSTM_ONE_TIME_STEP_BHAR_INPUT_GATE_HIDDEN_MULTIPLIER,
                                           LSTM_ONE_TIME_STEP_BHAR_INPUT_GATE_HIDDEN_SHIFT,
                                           &lstm_one_time_step_bhar_input_gate_hidden_weights[0],
                                           &input_hidden_kernel_sum[0],
                                           &lstm_one_time_step_bhar_input_gate_bias[0],
                                           ARM_SIGMOID};

    // FORGET GATE
    const cmsis_nn_lstm_gate gate_forget = {LSTM_ONE_TIME_STEP_BHAR_FORGET_GATE_INPUT_MULTIPLIER,
                                            LSTM_ONE_TIME_STEP_BHAR_FORGET_GATE_INPUT_SHIFT,
                                            &lstm_one_time_step_bhar_forget_gate_input_weights[0],
                                            &forget_data_kernel_sum[0],
                                            LSTM_ONE_TIME_STEP_BHAR_FORGET_GATE_HIDDEN_MULTIPLIER,
                                            LSTM_ONE_TIME_STEP_BHAR_FORGET_GATE_HIDDEN_SHIFT,
                                            &lstm_one_time_step_bhar_forget_gate_hidden_weights[0],
                                            &forget_hidden_kernel_sum[0],
                                            &lstm_one_time_step_bhar_forget_gate_bias[0],
                                            ARM_SIGMOID};

    // CELL GATE
    const cmsis_nn_lstm_gate gate_cell = {LSTM_ONE_TIME_STEP_BHAR_CELL_GATE_INPUT_MULTIPLIER,
                                          LSTM_ONE_TIME_STEP_BHAR_CELL_GATE_INPUT_SHIFT,
                                          &lstm_one_time_step_bhar_cell_gate_input_weights[0],
                                          &cell_data_kernel_sum[0],
                                          LSTM_ONE_TIME_STEP_BHAR_CELL_GATE_HIDDEN_MULTIPLIER,
                                          LSTM_ONE_TIME_STEP_BHAR_CELL_GATE_HIDDEN_SHIFT,
                                          &lstm_one_time_step_bhar_cell_gate_hidden_weights[0],
                                          &cell_hidden_kernel_sum[0],
                                          &lstm_one_time_step_bhar_cell_gate_bias[0],
                                          ARM_TANH};

    // OUTPUT GATE
    const cmsis_nn_lstm_gate gate_output = {LSTM_ONE_TIME_STEP_BHAR_OUTPUT_GATE_INPUT_MULTIPLIER,
                                            LSTM_ONE_TIME_STEP_BHAR_OUTPUT_GATE_INPUT_SHIFT,
                                            &lstm_one_time_step_bhar_output_gate_input_weights[0],
                                            &output_data_kernel_sum[0],
                                            LSTM_ONE_TIME_STEP_BHAR_OUTPUT_GATE_HIDDEN_MULTIPLIER,
                                            LSTM_ONE_TIME_STEP_BHAR_OUTPUT_GATE_HIDDEN_SHIFT,
                                            &lstm_one_time_step_bhar_output_gate_hidden_weights[0],
                                            &output_hidden_kernel_sum[0],
                                            &lstm_one_time_step_bhar_output_gate_bias[0],
                                            ARM_SIGMOID};

    // LSTM DATA
    const cmsis_nn_lstm_params params = {LSTM_ONE_TIME_STEP_BHAR_TIME_MAJOR,
                                         LSTM_ONE_TIME_STEP_BHAR_BATCH_SIZE,
                                         LSTM_ONE_TIME_STEP_BHAR_TIME_STEPS,
                                         LSTM_ONE_TIME_STEP_BHAR_INPUT_SIZE,
                                         LSTM_ONE_TIME_STEP_BHAR_HIDDEN_SIZE,
                                         LSTM_ONE_TIME_STEP_BHAR_INPUT_ZERO_POINT,
                                         LSTM_ONE_TIME_STEP_BHAR_FORGET_TO_CELL_MULTIPLIER,
                                         LSTM_ONE_TIME_STEP_BHAR_FORGET_TO_CELL_SHIFT,
                                         LSTM_ONE_TIME_STEP_BHAR_INPUT_TO_CELL_MULTIPLIER,
                                         LSTM_ONE_TIME_STEP_BHAR_INPUT_TO_CELL_SHIFT,
                                         LSTM_ONE_TIME_STEP_BHAR_CELL_CLIP,
                                         LSTM_ONE_TIME_STEP_BHAR_CELL_SCALE_POWER,
                                         LSTM_ONE_TIME_STEP_BHAR_OUTPUT_MULTIPLIER,
                                         LSTM_ONE_TIME_STEP_BHAR_OUTPUT_SHIFT,
                                         LSTM_ONE_TIME_STEP_BHAR_OUTPUT_ZERO_POINT,
                                         gate_forget,
                                         gate_input,
                                         gate_cell,
                                         gate_output};

    cmsis_nn_lstm_context buffers;
    buffers.temp1 = buffer1;
    buffers.temp2 = buffer2;
    buffers.cell_state = buffer3;

    arm_cmsis_nn_status result = arm_lstm_unidirectional_s8(lstm_one_time_step_bhar_input_tensor, output, &params, &buffers);
}
#endif


#ifdef FC_TEST
void FC_BHAR(void)
{
    const arm_cmsis_nn_status expected = ARM_CMSIS_NN_SUCCESS;
    int8_t output[FC_POLICY_BHAR_DST_SIZE] = {0};

    cmsis_nn_context ctx;
    cmsis_nn_fc_params fc_params;
    // cmsis_nn_per_tensor_quant_params quant_params;
    cmsis_nn_quant_params quant_params;
    cmsis_nn_dims input_dims;
    cmsis_nn_dims filter_dims;
    cmsis_nn_dims bias_dims;
    cmsis_nn_dims output_dims;

    const int32_t *bias_data = fc_policy_bhar_biases;
    const int8_t *kernel_data = fc_policy_bhar_weights;
    const int8_t *input_data = fc_policy_bhar_input_tensor;
    const int8_t *output_ref = fc_policy_bhar_output_ref;
    const int32_t output_ref_size = FC_POLICY_BHAR_DST_SIZE;

    input_dims.n = FC_POLICY_BHAR_INPUT_BATCHES;
    input_dims.w = FC_POLICY_BHAR_INPUT_W;
    input_dims.h = FC_POLICY_BHAR_INPUT_H;
    input_dims.c = FC_POLICY_BHAR_IN_CH;
    filter_dims.n = FC_POLICY_BHAR_ACCUMULATION_DEPTH;
    filter_dims.c = FC_POLICY_BHAR_OUT_CH;
    output_dims.n = FC_POLICY_BHAR_INPUT_BATCHES;
    output_dims.c = FC_POLICY_BHAR_OUT_CH;

    fc_params.input_offset = FC_POLICY_BHAR_INPUT_OFFSET;
    fc_params.filter_offset = 0;
    fc_params.output_offset = FC_POLICY_BHAR_OUTPUT_OFFSET;
    fc_params.activation.min = FC_POLICY_BHAR_OUT_ACTIVATION_MIN;
    fc_params.activation.max = FC_POLICY_BHAR_OUT_ACTIVATION_MAX;

    quant_params.multiplier = fc_policy_bhar_output_multiplier;
    quant_params.shift = fc_policy_bhar_output_shift;
    quant_params.is_per_channel = true;

    const int32_t buf_size = arm_fully_connected_s8_get_buffer_size(&filter_dims);
    ctx.buf = malloc(buf_size);
    ctx.size = buf_size;


    arm_cmsis_nn_status result = arm_fully_connected_wrapper_s8(&ctx,
                                                        &fc_params,
                                                        &quant_params,
                                                        &input_dims,
                                                        input_data,
                                                        &filter_dims,
                                                        kernel_data,
                                                        &bias_dims,
                                                        bias_data,
                                                        &output_dims,
                                                        output);

    if (ctx.buf)
    {
        // The caller is responsible to clear the scratch buffers for security reasons if applicable.
        memset(ctx.buf, 0, buf_size);
        free(ctx.buf);
    }
}
#endif