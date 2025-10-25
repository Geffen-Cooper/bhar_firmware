#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: Copyright 2010-2022 Arm Limited and/or its affiliates <open-source-office@arm.com>
#
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the License); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import sys
import json
import argparse
import subprocess

import numpy as np
import tensorflow as tf
from convert_to_tflite import CMSISFCLayer,CMSISCONVLayer

from generate_test_data import SoftmaxSettings, FullyConnectedSettings, ConvSettings, Interpreter, OpResolverType


class MODEL_EXTRACTOR(SoftmaxSettings, FullyConnectedSettings, ConvSettings):

    def __init__(self, dataset, schema_file, tflite_model):

        super().__init__(dataset, None, True, True, True, schema_file)

        self.tflite_model = tflite_model

        (self.quantized_multiplier, self.quantized_shift) = 0, 0
        self.is_int16xint8 = False  # Only 8-bit supported.
        self.diff_min, self.input_multiplier, self.input_left_shift = 0, 0, 0

        self.supported_ops = ["CONV_2D", "DEPTHWISE_CONV_2D", "FULLY_CONNECTED", "AVERAGE_POOL_2D", "SOFTMAX"]

    def from_bytes(self, tensor_data, type_size) -> list:
        total_bytes = 0
        result = []
        tmp_ints = []

        if type_size == 1:
            tensor_type = np.uint8
        elif type_size == 2:
            tensor_type = np.uint16
        elif type_size == 4:
            tensor_type = np.uint32
        else:
            raise RuntimeError("Size not supported: {}".format(type_size))

        count = 0
        for val in tensor_data:
            tmp_ints.append(val)
            count = count + 1
            if count % type_size == 0:
                tmp_bytes = bytearray(tmp_ints)
                result.append(int.from_bytes(tmp_bytes, 'little', signed=True))
                tmp_ints.clear()
                total_bytes += type_size
        self.total_bytes += total_bytes
        return result

    def tflite_to_json(self, tflite_input, schema):
        name_without_ext, ext = os.path.splitext(tflite_input)
        new_name = name_without_ext + '.json'
        dirname = os.path.dirname(tflite_input)

        if schema is None:
            raise RuntimeError("A schema file is required.")
        # command = f"flatc -o {dirname} --strict-json -t {schema} -- {tflite_input}"
        command = f"flatc -t --strict-json --defaults-json schema.fbs -- tflite_model"
        command_list = command.split(' ')
        try:
            process = subprocess.run(command_list)
            if process.returncode != 0:
                print(f"ERROR: {command = }")
                sys.exit(1)
        except Exception as e:
            raise RuntimeError(f"{e} from: {command = }. Did you install flatc?")

        return new_name

    def write_c_config_header(self, name_prefix, op_name, op_index) -> None:
        filename = f"{name_prefix}_config_data.h"

        self.generated_header_files.append(filename)
        filepath = self.headers_dir + filename

        prefix = f'{op_name}_{op_index}'

        print("Writing C header with config data {}...".format(filepath))
        with open(filepath, "w+") as f:
            self.write_c_common_header(f)
            f.write("#define {}_OUT_CH {}\n".format(prefix, self.output_ch))
            f.write("#define {}_IN_CH {}\n".format(prefix, self.input_ch))
            f.write("#define {}_INPUT_W {}\n".format(prefix, self.x_input-2*self.pad_x)) # adjust this manually because tflite prepads the input as an operation
            f.write("#define {}_INPUT_H {}\n".format(prefix, self.y_input))
            f.write("#define {}_DST_SIZE {}\n".format(prefix,
                                                      self.x_output * self.y_output * self.output_ch * self.batches))
            if op_name == "SOFTMAX":
                f.write("#define {}_NUM_ROWS {}\n".format(prefix, self.y_input))
                f.write("#define {}_ROW_SIZE {}\n".format(prefix, self.x_input))
                f.write("#define {}_MULT {}\n".format(prefix, self.input_multiplier))
                f.write("#define {}_SHIFT {}\n".format(prefix, self.input_left_shift))
                if not self.is_int16xint8:
                    f.write("#define {}_DIFF_MIN {}\n".format(prefix, -self.diff_min))
            else:
                f.write("#define {}_FILTER_X {}\n".format(prefix, self.filter_x))
                f.write("#define {}_FILTER_Y {}\n".format(prefix, self.filter_y))
                f.write("#define {}_FILTER_W {}\n".format(prefix, self.filter_x))
                f.write("#define {}_FILTER_H {}\n".format(prefix, self.filter_y))
                f.write("#define {}_STRIDE_X {}\n".format(prefix, self.stride_x))
                f.write("#define {}_STRIDE_Y {}\n".format(prefix, self.stride_y))
                f.write("#define {}_STRIDE_W {}\n".format(prefix, self.stride_x))
                f.write("#define {}_STRIDE_H {}\n".format(prefix, self.stride_y))
                f.write("#define {}_PAD_X {}\n".format(prefix, self.pad_x))
                f.write("#define {}_PAD_Y {}\n".format(prefix, self.pad_y))
                f.write("#define {}_PAD_W {}\n".format(prefix, self.pad_x))
                f.write("#define {}_PAD_H {}\n".format(prefix, self.pad_y))
                f.write("#define {}_OUTPUT_W {}\n".format(prefix, self.x_output))
                f.write("#define {}_OUTPUT_H {}\n".format(prefix, self.y_output))
                f.write("#define {}_INPUT_OFFSET {}\n".format(prefix, -self.input_zero_point))
                f.write("#define {}_INPUT_SIZE {}\n".format(prefix, self.x_input * self.y_input * self.input_ch))
                f.write("#define {}_OUT_ACTIVATION_MIN {}\n".format(prefix, self.out_activation_min))
                f.write("#define {}_OUT_ACTIVATION_MAX {}\n".format(prefix, self.out_activation_max))
                f.write("#define {}_INPUT_BATCHES {}\n".format(prefix, self.batches))
                f.write("#define {}_OUTPUT_OFFSET {}\n".format(prefix, self.output_zero_point))
                f.write("#define {}_DILATION_X {}\n".format(prefix, self.dilation_x))
                f.write("#define {}_DILATION_Y {}\n".format(prefix, self.dilation_y))
                f.write("#define {}_DILATION_W {}\n".format(prefix, self.dilation_x))
                f.write("#define {}_DILATION_H {}\n".format(prefix, self.dilation_y))

            if op_name == "FULLY_CONNECTED":
                f.write("#define {}_OUTPUT_MULTIPLIER {}\n".format(prefix, self.quantized_multiplier))
                f.write("#define {}_OUTPUT_SHIFT {}\n".format(prefix, self.quantized_shift))

            if op_name == "DEPTHWISE_CONV_2D":
                f.write("#define {}_ACCUMULATION_DEPTH {}\n".format(prefix,
                                                                    self.input_ch * self.x_input * self.y_input))

        # self.format_output_file(filepath)

    def shape_to_config(self, input_shape, filter_shape, output_shape, layer_name):
        if layer_name == "AVERAGE_POOL_2D":
            [_, self.filter_y, self.filter_x, _] = input_shape

        elif layer_name == "CONV_2D" or layer_name == "DEPTHWISE_CONV_2D":
            [self.batches, self.y_input, self.x_input, self.input_ch] = input_shape
            [output_ch, self.filter_y, self.filter_x, self.input_ch] = filter_shape

        elif layer_name == "FULLY_CONNECTED":
            [self.batches, self.input_ch] = input_shape
            [self.input_ch, self.output_ch] = filter_shape
            [self.y_output, self.x_output] = output_shape
            self.x_input = 1
            self.y_input = 1

        elif layer_name == "SOFTMAX":
            [self.y_input, self.x_input] = input_shape

        if len(input_shape) == 4:
            if len(output_shape) == 2:
                [self.y_output, self.x_output] = output_shape
            else:
                [d, self.y_output, self.x_output, d1] = output_shape

        self.set_output_dims_and_padding(self.x_output, self.y_output)

    def extract_from_model(self, json_file, tensor_details):

        with open(json_file, 'r') as in_file:
            data = in_file.read()
            data = json.loads(data)
            tensors = data['subgraphs'][0]['tensors']
            operators = data['subgraphs'][0]['operators']
            operator_codes = data['operator_codes']
            buffers = data['buffers']

        # store the layers as a list
        cmsis_layers_list = []
        self.total_bytes = 0

        # prepare the C code
        max_buffer_size = 0
        max_ctx_buffer_size = 0
        in_scale = 0
        pad_same = False
        run_nn_filename = f"TestCases/TestData/{self.testdataset}/run_nn.h"
        with open(run_nn_filename, "w+") as f:
            f.write('#include <stdint.h>\n')
            f.write('#include <stdlib.h>\n')
            f.write('#include "test_data.h"\n')
            f.write('#include "arm_nnsupportfunctions.h"\n')
            f.write('#include "arm_nnfunctions.h"\n\n\n\n\n')
            f.write("// layer parameters\n")
            f.write("cmsis_nn_context ctx;\n")
            f.write("cmsis_nn_conv_params conv_params;\n")
            f.write("cmsis_nn_per_channel_quant_params quant_params;\n")
            f.write("cmsis_nn_dims input_dims;\n")
            f.write("cmsis_nn_dims filter_dims;\n")
            f.write("cmsis_nn_dims bias_dims;\n")
            f.write("cmsis_nn_dims output_dims;\n\n")
            # f.write("int32_t buf_size;\n\n")
            f.write('int8_t* run_nn(int8_t* data_buffer, int8_t* input_buffer, int8_t* output_buffer)\n{\n')

        supported_op = False
        op_index = 0
        for op in operators:
            if 'opcode_index' in op:
                builtin_name = operator_codes[op['opcode_index']]['builtin_code']
            else:
                builtin_name = ""
            #op_name = 'layer_' + str(op_index) + '_' + builtin_name

            # save the layer params for this op
            if builtin_name == "FULLY_CONNECTED":
                layer_params = {"weights":None, "bias":None, "in_scale":None, "in_zp":None, "out_scale":None, "out_zp":None, "multiplier":None, "shift":None}
            if builtin_name == "CONV_2D":
                layer_params = {"weights":None, "bias":None, "in_scale":None, "in_zp":None, "out_scale":None, "out_zp":None, "channel_multipliers":None, "channel_shifts":None,
                                "padding_type":None,"stride":None}

            if builtin_name == "PAD":
                pad_same = True

            # Get stride and padding.
            if 'builtin_options' in op:
                builtin_options = op['builtin_options']
                if 'stride_w' in builtin_options:
                    self.stride_x = builtin_options['stride_w']
                    # add stride param
                    layer_params["stride"] = self.stride_x
                if 'stride_h' in builtin_options:
                    self.stride_y = builtin_options['stride_h']
                    if 'padding' in builtin_options:
                        self.has_padding = False
                        self.padding = 'VALID'
                        # add padding param
                        layer_params["padding_type"] = self.padding
                    else:
                        self.has_padding = True
                        self.padding = 'SAME'
                        # add padding param
                        layer_params["padding_type"] = self.padding

                    # need to do this manually since flatx buffer
                    # treats padding as a separate operation
                    if pad_same == True:
                        pad_same = False
                        self.has_padding = True
                        self.padding = 'SAME'
                        layer_params["padding_type"] = self.padding

            # Generate weights, bias, multipliers, shifts and config.
            if builtin_name not in self.supported_ops:
                print(f"WARNING: skipping unsupported operator {builtin_name}")
            else:
                supported_op = True

                input_index = op['inputs'][0]
                output_index = op['outputs'][0]

                input_tensor = tensor_details[input_index]
                output_tensor = tensor_details[output_index]
                input_scale = input_tensor['quantization'][0]
                output_scale = output_tensor['quantization'][0]
                self.input_zero_point = input_tensor['quantization'][1]
                self.output_zero_point = output_tensor['quantization'][1]

                if op_index == 0:
                    in_scale = input_scale

                # store the quant params
                layer_params['in_scale'] = input_scale
                layer_params['out_scale'] = output_scale
                layer_params['in_zp'] = self.input_zero_point
                layer_params['out_zp'] = self.output_zero_point

                input_shape = input_tensor['shape']
                output_shape = output_tensor['shape']

                if builtin_name == "CONV_2D" or builtin_name == "DEPTHWISE_CONV_2D" \
                   or builtin_name == "FULLY_CONNECTED":
                    weights_index = op['inputs'][1]
                    bias_index = op['inputs'][2]

                    bias = tensors[bias_index]
                    weights = tensors[weights_index]

                    weights_data_index = weights['buffer']
                    weights_data_buffer = buffers[weights_data_index]
                    weights_data = self.from_bytes(weights_data_buffer['data'], 1)

                    bias_data_index = bias['buffer']
                    bias_data_buffer = buffers[bias_data_index]
                    bias_data = self.from_bytes(bias_data_buffer['data'], 4)

                    scaling_factors = weights['quantization']['scale']

                    self.output_ch = len(scaling_factors)

                    filter_shape = weights['shape']

                    # store the parameter values
                    layer_params['weights'] = np.array(weights_data).reshape(weights['shape'])
                    layer_params['bias'] = np.array(bias_data)
                else:
                    filter_shape = []

                self.input_scale, self.output_scale = input_scale, output_scale

                if builtin_name == "SOFTMAX":
                    self.calc_softmax_params()

                self.shape_to_config(input_shape, filter_shape, output_shape, builtin_name)

                nice_name = 'layer_' + str(op_index) + '_' + builtin_name.lower()

                if builtin_name == "CONV_2D" or builtin_name == "DEPTHWISE_CONV_2D" \
                   or builtin_name == "FULLY_CONNECTED":
                    self.generate_c_array(nice_name + "_weights", weights_data)
                    self.generate_c_array(nice_name + "_bias", bias_data, datatype='int32_t')

                if builtin_name == "FULLY_CONNECTED":
                    self.weights_scale = scaling_factors[0]
                    self.quantize_multiplier()

                    # store the requant params and add a layer to the list
                    layer_params['multiplier'] = self.quantized_multiplier
                    layer_params['shift'] = self.quantized_shift
                    cmsis_layers_list.append(CMSISFCLayer(**layer_params))

                    # write the layer to C code
                    if op_index % 2 == 0:
                        if op_index == 0:
                            in_buff = "data_buffer"
                            out_buff = "output_buffer"
                        else:
                            in_buff = "input_buffer"
                            out_buff = "output_buffer"
                    else:
                        in_buff = "output_buffer"
                        out_buff = "input_buffer"
                    with open(run_nn_filename, "a") as f:
                        f.write("\t// Layer {}\n".format(op_index))
                        if op_index == 0:
                            f.write("\tarm_status out = arm_nn_vec_mat_mult_t_s8({}, // input buffer for layer\n".format(in_buff))
                        else:
                            f.write("\t                    out = arm_nn_vec_mat_mult_t_s8({},\n".format(in_buff))
                        f.write("\t                                                   {}, // weight buffer for layer\n".format(self.testdataset + '_' + nice_name + "_weights"))
                        f.write("\t                                                   {}, // bias buffer for layer\n".format(self.testdataset + '_' + nice_name + "_bias"))
                        f.write("\t                                                   {}, // output buffer for layer\n".format(out_buff))
                        f.write("\t                                                   {}, // input zero point (flipped)\n".format(-self.input_zero_point))
                        f.write("\t                                                   {}, // weight zero point (none)\n".format(0))
                        f.write("\t                                                   {}, // output zero point\n".format(self.output_zero_point))
                        f.write("\t                                                   {}, // requantization multiplier\n".format(self.quantized_multiplier))
                        f.write("\t                                                   {}, // requantization shift\n".format(self.quantized_shift))
                        f.write("\t                                                   {}, // weight matrix columns\n".format(self.output_ch))
                        f.write("\t                                                   {}, // weight matrix rows\n".format(self.input_ch))
                        f.write("\t                                                   {}, // min activation value\n".format(self.out_activation_min))
                        f.write("\t                                                   {}, // max activation value\n".format(self.out_activation_max))
                        f.write("\t                                                   {});\n\n".format(1))
                        
                        if self.output_ch > max_buffer_size:
                            max_buffer_size = self.output_ch
                        if self.input_ch > max_buffer_size:
                            max_buffer_size = self.input_ch

                elif builtin_name == "CONV_2D" or builtin_name == "DEPTHWISE_CONV_2D":
                    self.scaling_factors = scaling_factors
                    per_channel_multiplier, per_channel_shift = self.generate_quantize_per_channel_multiplier()

                    self.generate_c_array(f"{nice_name}_output_mult", per_channel_multiplier, datatype='int32_t')
                    self.generate_c_array(f"{nice_name}_output_shift", per_channel_shift, datatype='int32_t')

                    # store the requant params and add a layer to the list
                    layer_params['channel_multipliers'] = per_channel_multiplier
                    layer_params['channel_shifts'] = per_channel_shift

                    # print(layer_params)
                    cmsis_layers_list.append(CMSISCONVLayer(**layer_params))

                    # write the layer to C code
                    if op_index % 2 == 0:
                        if op_index == 0:
                            in_buff = "data_buffer"
                            out_buff = "output_buffer"
                        else:
                            in_buff = "input_buffer"
                            out_buff = "output_buffer"
                    else:
                        in_buff = "output_buffer"
                        out_buff = "input_buffer"
                    with open(run_nn_filename, "a") as f:

                        f.write("\t// Layer {}\n".format(op_index))
                        f.write("\tinput_dims.n = CONV_2D_{}_INPUT_BATCHES;\n".format(op_index))
                        f.write("\tinput_dims.w = CONV_2D_{}_INPUT_W;\n".format(op_index))
                        f.write("\tinput_dims.h = CONV_2D_{}_INPUT_H;\n".format(op_index))
                        f.write("\tinput_dims.c = CONV_2D_{}_IN_CH;\n".format(op_index))
                        f.write("\tfilter_dims.w = CONV_2D_{}_FILTER_X;\n".format(op_index))
                        f.write("\tfilter_dims.h = CONV_2D_{}_FILTER_Y;\n".format(op_index))
                        f.write("\toutput_dims.w = CONV_2D_{}_OUTPUT_W;\n".format(op_index))
                        f.write("\toutput_dims.h = CONV_2D_{}_OUTPUT_H;\n".format(op_index))
                        f.write("\toutput_dims.c = CONV_2D_{}_OUT_CH;\n\n".format(op_index))

                        f.write("\tconv_params.padding.w = CONV_2D_{}_PAD_X;\n".format(op_index))
                        f.write("\tconv_params.padding.h = CONV_2D_{}_PAD_Y;\n".format(op_index))
                        f.write("\tconv_params.stride.w = CONV_2D_{}_STRIDE_X;\n".format(op_index))
                        f.write("\tconv_params.stride.h = CONV_2D_{}_STRIDE_Y;\n".format(op_index))
                        f.write("\tconv_params.dilation.w = CONV_2D_{}_DILATION_X;\n".format(op_index))
                        f.write("\tconv_params.dilation.h = CONV_2D_{}_DILATION_Y;\n\n".format(op_index))

                        f.write("\tconv_params.input_offset = CONV_2D_{}_INPUT_OFFSET;\n".format(op_index))
                        f.write("\tconv_params.output_offset = CONV_2D_{}_OUTPUT_OFFSET;\n".format(op_index))
                        f.write("\tconv_params.activation.min = CONV_2D_{}_OUT_ACTIVATION_MIN;\n".format(op_index))
                        f.write("\tconv_params.activation.max = CONV_2D_{}_OUT_ACTIVATION_MAX;\n".format(op_index))
                        f.write("\tquant_params.multiplier = (int32_t *){}_output_mult;\n".format(self.testdataset + '_' + nice_name))
                        f.write("\tquant_params.shift = (int32_t *){}_output_shift;\n\n".format(self.testdataset + '_' + nice_name))
                        if op_index > 0:
                            # f.write("\tif (ctx.buf)\n")
                            # f.write("\t{\n")
                            f.write("\tmemset(ctx.buf, 0, {});\n".format(max_ctx_buffer_size))
                            # f.write("\t\tfree(ctx.buf);\n")
                            # f.write("\t}\n")
                        else:
                            f.write("\tctx.buf = ctx_buf;\n")
                            f.write("\tctx.size = 0;\n")
                        # f.write("\tbuf_size = arm_convolve_s8_get_buffer_size(&input_dims, &filter_dims);\n")
                        # f.write("\tctx.buf = malloc(buf_size);\n")
                        # f.write("\tctx.size = 0;\n\n")
                        if op_index == 0:
                            f.write("\tarm_status out = arm_convolve_s8(&ctx, // extra buffer for convolution\n")
                        else:
                            f.write("\t                    out = arm_convolve_s8(&ctx, // extra buffer for convolution\n")

                        f.write("\t                                          &conv_params, // stride, padding, etc.\n")
                        f.write("\t                                          &quant_params, // per channel quantization values\n")
                        f.write("\t                                          &input_dims,\n")
                        if op_index == 0:
                            f.write("\t                                          {}, // input buffer for layer\n".format(in_buff))
                        else:
                            f.write("\t                                          {},\n".format(in_buff))
                        f.write("\t                                          &filter_dims,\n")
                        f.write("\t                                          {}, // weight buffer for layer\n".format(self.testdataset + '_' + nice_name + "_weights"))
                        f.write("\t                                          &bias_dims,\n")
                        f.write("\t                                          {}, // bias buffer for layer\n".format(self.testdataset + '_' + nice_name + "_bias"))
                        f.write("\t                                          &output_dims,\n")
                        f.write("\t                                          {}); // output buffer for layer\n\n".format(out_buff))
                        if self.x_output * self.y_output * self.output_ch > max_buffer_size:
                            max_buffer_size = self.x_output * self.y_output * self.output_ch
                        if self.x_input * self.y_input * self.input_ch > max_buffer_size:
                            max_buffer_size = self.x_input * self.y_input * self.input_ch
                        if 2 * self.input_ch * self.filter_x * self.filter_y * 2 > max_ctx_buffer_size:
                            max_ctx_buffer_size = 2 * self.input_ch * self.filter_x * self.filter_y * 2
                            

                self.write_c_config_header(nice_name, builtin_name, op_index)
            if supported_op == True:
                supported_op = False
                op_index = op_index + 1

        # add the return
        with open(run_nn_filename, "a") as f:
            if op_index % 2 == 0:
                f.write("\treturn input_buffer;\n}")
            else:
                f.write("\treturn output_buffer;\n}")

        # add the input and output buffers
        # Read the contents of the file
        with open(run_nn_filename, 'r') as file:
            lines = file.readlines()

        # Modify the sixth line (index 5)
        lines[6] = "int8_t nn_input_buffer[{}] = {{0}};\n".format(max_buffer_size)
        lines[7] = "int8_t nn_output_buffer[{}] = {{0}};\n".format(max_buffer_size)
        lines[8] = "int32_t fixed_point_scale = {};\n".format(round((1/(128*in_scale))*2**15))
        # lines[9] = "uint8_t ctx_buf[{}] = {{0}};\n\n".format(max_ctx_buffer_size)

        # Write the updated contents back to the file
        with open(run_nn_filename, 'w') as file:
            file.writelines(lines)

        # remove const from the input
        with open(f"TestCases/TestData/{self.testdataset}/input_data.h", 'r') as file:
            lines = file.readlines()

        # Remove 'const' from each line
        modified_lines = [line.replace('const ', '') for line in lines]

        # Write the modified lines back to the file
        with open(f"TestCases/TestData/{self.testdataset}/input_data.h", 'w') as file:
            file.writelines(modified_lines)
        print(f"Model Size: {self.total_bytes/1e3} KB")
        return cmsis_layers_list

    def generate_data(self, input_data=None, weights=None, biases=None) -> None:

        interpreter = Interpreter(model_path=str(self.tflite_model),
                                  experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
        interpreter.allocate_tensors()

        # Needed for input/output scale/zp as equivalant json file data has too low precision.
        tensor_details = interpreter.get_tensor_details()

        output_details = interpreter.get_output_details()
        (self.output_scale, self.output_zero_point) = output_details[0]['quantization']

        input_details = interpreter.get_input_details()
        if len(input_details) != 1:
            raise RuntimeError(f"Only single input supported.")
        input_shape = input_details[0]['shape']
        input_data = self.get_randomized_input_data(input_data, input_shape)
        interpreter.set_tensor(input_details[0]["index"], tf.cast(input_data, tf.int8))

        self.generate_c_array("input", tf.reshape(tf.transpose(input_data),[-1]))
        # self.generate_c_array("input", tf.reshape(tf.transpose(tf.reshape(input_data, [-1])), input_data.shape))


        json_file = self.tflite_to_json(self.tflite_model, self.schema_file)
        cmsis_layer_list = self.extract_from_model(json_file, tensor_details)

        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]["index"])
        self.generate_c_array("output_ref", np.clip(output_data, self.out_activation_min, self.out_activation_max))

        self.write_c_header_wrapper()

        return cmsis_layer_list


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extract operator data from given model if operator is supported."
                                     "This provides a way for CMSIS-NN to directly process a model.")
    parser.add_argument('--schema-file', type=str, required=True, help="Path to schema file.")
    parser.add_argument('--tflite-model', type=str, required=True, help="Path to tflite file.")
    parser.add_argument('--model-name',
                        type=str,
                        help="Descriptive model name. If left out it will be inferred from actual model.")

    args = parser.parse_args()

    schema_file = args.schema_file
    tflite_model = args.tflite_model

    if args.model_name:
        dataset = args.model_name
    else:
        dataset, _ = os.path.splitext(os.path.basename(tflite_model))

    model_extractor = MODEL_EXTRACTOR(dataset, schema_file, tflite_model)
    model_extractor.generate_data()