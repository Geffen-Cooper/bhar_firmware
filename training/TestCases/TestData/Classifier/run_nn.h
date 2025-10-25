#include <stdint.h>
#include <stdlib.h>
#include "test_data.h"
#include "arm_nnsupportfunctions.h"
#include "arm_nnfunctions.h"

int8_t nn_input_buffer[75] = {0};
int8_t nn_output_buffer[75] = {0};
int32_t fixed_point_scale = 12551;
// layer parameters
cmsis_nn_context ctx;
cmsis_nn_conv_params conv_params;
cmsis_nn_per_channel_quant_params quant_params;
cmsis_nn_dims input_dims;
cmsis_nn_dims filter_dims;
cmsis_nn_dims bias_dims;
cmsis_nn_dims output_dims;

int8_t* run_nn(int8_t* data_buffer, int8_t* input_buffer, int8_t* output_buffer)
{
	// Layer 0
	arm_status out = arm_nn_vec_mat_mult_t_s8(data_buffer, // input buffer for layer
	                                                   Classifier_layer_0_fully_connected_weights, // weight buffer for layer
	                                                   Classifier_layer_0_fully_connected_bias, // bias buffer for layer
	                                                   output_buffer, // output buffer for layer
	                                                   -4, // input zero point (flipped)
	                                                   0, // weight zero point (none)
	                                                   -128, // output zero point
	                                                   1248317035, // requantization multiplier
	                                                   -8, // requantization shift
	                                                   75, // weight matrix columns
	                                                   64, // weight matrix rows
	                                                   -128, // min activation value
	                                                   127, // max activation value
	                                                   1);

	// Layer 1
	                    out = arm_nn_vec_mat_mult_t_s8(output_buffer,
	                                                   Classifier_layer_1_fully_connected_weights, // weight buffer for layer
	                                                   Classifier_layer_1_fully_connected_bias, // bias buffer for layer
	                                                   input_buffer, // output buffer for layer
	                                                   128, // input zero point (flipped)
	                                                   0, // weight zero point (none)
	                                                   -128, // output zero point
	                                                   1370942136, // requantization multiplier
	                                                   -8, // requantization shift
	                                                   64, // weight matrix columns
	                                                   16, // weight matrix rows
	                                                   -128, // min activation value
	                                                   127, // max activation value
	                                                   1);

	// Layer 2
	                    out = arm_nn_vec_mat_mult_t_s8(input_buffer,
	                                                   Classifier_layer_2_fully_connected_weights, // weight buffer for layer
	                                                   Classifier_layer_2_fully_connected_bias, // bias buffer for layer
	                                                   output_buffer, // output buffer for layer
	                                                   128, // input zero point (flipped)
	                                                   0, // weight zero point (none)
	                                                   -2, // output zero point
	                                                   1242373775, // requantization multiplier
	                                                   -8, // requantization shift
	                                                   16, // weight matrix columns
	                                                   6, // weight matrix rows
	                                                   -128, // min activation value
	                                                   127, // max activation value
	                                                   1);

	return output_buffer;
}