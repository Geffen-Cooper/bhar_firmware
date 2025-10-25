'''
PyTorch --> CMSIS-NN
1. Convert the pytorch model to onnx
    -verify that operators used are supported
2. Convert from onnx to tensorflow
    -create an equivalent model in tensorflow
3. Convert from tensorflow to tflite and quantize
    -ensure no accuracy is lost
4. Convert tflite to CMSIS-NN
    -derive quantization params, verify behavior
    -generate C code
'''

import torch
from torch import nn
import os
# os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from dataset import *
from train import *
from model import *
import copy
import tensorflow as tf
import onnx
import onnxruntime as ort
from onnx_tf.backend import prepare
from tensorflow.lite.python.interpreter import Interpreter
from tensorflow.lite.python.interpreter import OpResolverType
import sys
import json
import subprocess
from tensorflow.lite.python import schema_py_generated as schema
from abc import ABC, abstractmethod
from converter import *
import shutil


class ModelConverter:
    def __init__(self):
        self.HEADER = '\033[95m'
        self.OKBLUE = '\033[94m'
        self.OKCYAN = '\033[96m'
        self.OKGREEN = '\033[92m'
        self.WARNING = '\033[93m'
        self.FAIL = '\033[91m'
        self.ENDC = '\033[0m'
        self.BOLD = '\033[1m'
        self.UNDERLINE = '\033[4m'

    def pytorch_to_onnx(self,pytorch_model,dummy_input):
        self.model_name = pytorch_model.__class__.__name__
        self.dummy_input = dummy_input.numpy()

        # first move to cpu
        pytorch_model = pytorch_model.to('cpu').eval()

        # get dummy_output
        with torch.no_grad():
            self.dummy_output = pytorch_model(dummy_input).to('cpu').numpy()

        # convert to onnx
        torch.onnx.export(
            pytorch_model,          # PyTorch Model
            dummy_input,            # Input tensor
            "output.onnx",          # Output file (eg. 'output_model.onnx')
            opset_version=12,       # Operator support version
            input_names=['input'],  # Input tensor name (arbitary)
            output_names=['output'] # Output tensor name (arbitary)
        )

        # Load the ONNX model
        self.onnx_model = onnx.load("output.onnx")

        # Check that the IR is well formed
        onnx.checker.check_model(self.onnx_model)

        # prepare onnx model for inference
        ort_session = ort.InferenceSession('output.onnx')

        # compute ONNX Runtime output prediction
        ort_inputs = {ort_session.get_inputs()[0].name: self.dummy_input}
        ort_outs = ort_session.run(None, ort_inputs)

        try:
            # compare ONNX Runtime and PyTorch results
            np.testing.assert_allclose(self.dummy_output, ort_outs[0], rtol=1e-03, atol=1e-05)
        except Exception as e:
            print(e)
            print(f"{self.BOLD}{self.FAIL}===================== Failed to Convert to ONNX ====================={self.ENDC}")
            exit()

        print(f"{self.BOLD}{self.OKGREEN}===================== Converted to ONNX successfully ====================={self.ENDC}")

    def onnx_to_tensorflow(self):
        # load onnx to tensorflow
        tf_rep = prepare(self.onnx_model)
        tf_rep.export_graph("tf_model")
        model = tf.saved_model.load("tf_model")
        model.trainable = False

        # validate input-output
        dummy_input = tf.convert_to_tensor(self.dummy_input)
        dummy_output = model(**{'input': dummy_input})['output']

        try:
            # compare TF Runtime and PyTorch results
            np.testing.assert_allclose(self.dummy_output, dummy_output, rtol=1e-03, atol=1e-05)
        except Exception as e:
            print(e)
            print(f"{self.BOLD}{self.FAIL}===================== Failed to Convert to tensorflow ====================={self.ENDC}")
            exit()

        print(f"{self.BOLD}{self.OKGREEN}===================== Converted to TensorFlow successfully ====================={self.ENDC}")

    def tensorflow_to_quantized_tflite(self,train_loader,val_loader,desired_val_accuracy):
        # ================== convert to tflite and quantize ==================
        converter = tf.lite.TFLiteConverter.from_saved_model("tf_model")
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        
        def representative_dataset_gen():
            d,t = next(iter(train_loader))
            for i in range(len(t)):
                # get sample input data as numpy array 
                # unsqueeze needed for conv
                # d[i] = 
                # print(d[i].unsqueeze(0).permute(0,2,1).shape)
                # yield [d[i].unsqueeze(0).permute(0,2,1).numpy().astype(np.float32)]
                yield [d[i].unsqueeze(0).numpy().astype(np.float32)]

        converter.representative_dataset = representative_dataset_gen
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
        tflite_quant_model = converter.convert()

        with open("tflite_model", 'wb') as f:
            f.write(tflite_quant_model)


        # ================== instantiate the interpreter ==================
        interpreter = tf.lite.Interpreter(model_path="tflite_model",experimental_preserve_all_tensors=True)
        interpreter.allocate_tensors()

        # print(interpreter.get_input_details())
        # interpreter.resize_tensor_input(interpreter.get_input_details()[0]['index'],(10,3))
        # print(interpreter.get_input_details())
        # exit()

        # build the calibration set
        # train_loader, val_loader = load_gestures_nrf(0.75, 256, ["accelerometer_logs/class0_nothing.log","accelerometer_logs/class1_FB.log","accelerometer_logs/class2_LR.log","accelerometer_logs/class3_UD.log"])
        # d,t = next(iter(val_loader))
        # dq = np.int8(d*128)

        # collect model details
        input_details = interpreter.get_input_details()[0]
        output_details = interpreter.get_output_details()[0]
        input_scale, input_zero_point = input_details["quantization"]
        
        # find the input calibration constants 46943
        fixed_point_scale = round((1/(128*input_scale))*2**15)
        print(f"Fixed Point Scale: {fixed_point_scale}, Input Scale: {input_scale}, Input Zero point: {input_zero_point}")
        num_correct = 0
        total = 0
        
        sample_inputs = []
        sample_outputs = []
        for data,target in val_loader:
            for idx in range(len(target)):
                # print(idx)
                # rescale the input to [-128,127] (model expects quantized input)
                q_input = np.clip((((np.int32(data[idx]*128) << 8)*fixed_point_scale)>>(15+8))+input_zero_point,-128,127) # we add the zero point because this is "quantization" from fp32, q = (r/s) + zp
                # q_input = np.clip(np.int32(data[idx]/input_scale + input_zero_point),-128,127)
                # print(q_input,target[idx])
                # plt.plot(q_input[:25])
                # plt.plot(q_input[25:50])
                # plt.plot(q_input[50:])
                # plt.show()
                
                # print(q_input)
                sample_inputs.append(q_input)

                # forward pass
                q_input = np.expand_dims(q_input, axis=0).astype(input_details["dtype"])
                interpreter.set_tensor(input_details["index"], q_input)
                interpreter.invoke()

                # get output
                output = interpreter.get_tensor(output_details["index"])[0]

                sample_outputs.append(output)

                num_correct += (np.argmax(np.array(output)) == target[idx].item())
                total += 1

        q_acc = num_correct/total
        if q_acc < desired_val_accuracy:
            print(f"{self.BOLD}{self.FAIL}Quantized Accuracy: {q_acc} ({num_correct}/{total}){self.ENDC}")
        else:
            print(f"{self.BOLD}{self.OKGREEN}Quantized Accuracy: {q_acc} ({num_correct}/{total}){self.ENDC}")

        # for det in interpreter.get_tensor_details():
        #     print(det)
        #     print()
        # exit()

        return sample_inputs,sample_outputs

    def tflite_to_cmsisnn(self,sample_inputs,sample_outputs):
        extractor = MODEL_EXTRACTOR(self.model_name,"schema.fbs","tflite_model")
        cmsis_layer_list = extractor.generate_data()
        cmsis_net = CMSISNetwork(cmsis_layer_list)
        cmsis_net.test_model(sample_inputs,sample_outputs,self)

        # input = np.array([[-95, -41, -3,  70, -55, -39, -39, -19, -34, -108],
        #                  [75,  4, 8, 103, 120, -18, 102, 123, 77, -3],
        #                 [14,  81,  121, -51, -112, -54, 9, -16, 113, 5]])
        # # input = input.T.flatten().reshape(input.shape)
        # output = np.array([93, -93, -48, 94])
        # # cmsis_net.cmsis_layer_list[0].input_zp = 0
        # # print(sample_inputs[0],sample_outputs[0])
        # cmsis_net.test_model([input],[output],self,True)
        
        


def convert_model(path):
    # ================== convert model ==================
    # first load the pytorch model and its input dimension
    m = Classifier(25)
    state_dict = torch.load("models/baseline.pth")['model_state_dict']
    m = m.to('cpu')
    m.load_state_dict(state_dict)
    sample_input = torch.rand((1, 30))

    # convert to onnx
    torch.onnx.export(
        m,                  # PyTorch Model
        sample_input,                    # Input tensor
        "output.onnx",        # Output file (eg. 'output_model.onnx')
        opset_version=12,       # Operator support version
        input_names=['input'],   # Input tensor name (arbitary)
        output_names=['output'] # Output tensor name (arbitary)
    )

    # ================== validate model ==================

    # Load the ONNX model
    m = onnx.load("output.onnx")

    # Check that the IR is well formed
    onnx.checker.check_model(m)

    ort_session = ort.InferenceSession('output.onnx')

    outputs = ort_session.run(
        None,
        {'input': np.random.randn(1, 30).astype(np.float32)}
    )

    # ================== convert to tf model ==================

    onnx_model = onnx.load('output.onnx')
    tf_rep = prepare(onnx_model)
    tf_rep.export_graph("tf_model")

    model = tf.saved_model.load("tf_model")
    model.trainable = False

    input_tensor = tf.random.uniform([1,30])
    out = model(**{'input': input_tensor})


    # ================== convert to tflite and quantize ==================
    converter = tf.lite.TFLiteConverter.from_saved_model("tf_model")
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    def representative_dataset_gen():
        train_loader, val_loader = load_gestures_nrf(0.75, 512, ["accelerometer_logs/class0_nothing.log","accelerometer_logs/class1_FB.log","accelerometer_logs/class2_LR.log","accelerometer_logs/class3_UD.log"])
        d,t = next(iter(train_loader))
        for i in range(256):
            # get sample input data as numpy array 
            yield [d[i].numpy().astype(np.float32)]

    converter.representative_dataset = representative_dataset_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite_quant_model = converter.convert()

    with open("tflite_model", 'wb') as f:
        f.write(tflite_quant_model)

def eval_model(path):
    # ================== instantiate the interpreter ==================
    interpreter = tf.lite.Interpreter(model_path="tflite_model",experimental_preserve_all_tensors=True)
    interpreter.allocate_tensors()

    # build the calibration set
    train_loader, val_loader = load_gestures_nrf(0.75, 256, ["accelerometer_logs/class0_nothing.log","accelerometer_logs/class1_FB.log","accelerometer_logs/class2_LR.log","accelerometer_logs/class3_UD.log"])
    d,t = next(iter(val_loader))
    dq = np.int8(d*128)

    # collect model details
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]
    details = interpreter.get_tensor_details()
    input_scale, input_zero_point = input_details["quantization"]
    
    # find the input calibration constants
    fixed_point_scale = round((1/(128*input_scale))*2**15)

    # for d in details:
    #     print(d)
    #     print()
    # exit()

    num_correct = 0
    ti4 = None
    
    for id in range(len(t)):
        # rescale the input to [-128,127] (model expects quantized input)
        ti = (((np.int32(dq[id]) << 8)*fixed_point_scale)>>(15+8))+input_zero_point # we add the zero point because this is "quantization" from fp32, q = (r/s) + zp
        
        # forward pass
        ti = np.expand_dims(ti, axis=0).astype(input_details["dtype"])
        interpreter.set_tensor(input_details["index"], ti)
        interpreter.invoke()

        # get output
        output = interpreter.get_tensor(output_details["index"])[0]

        if(id == 40):
            ti4 = copy.deepcopy(ti)
            # a1 = interpreter.get_tensor(7)
            a1 = output
            print(t[id])
            # print("act:",interpreter.get_tensor(7))
            # print("input:",interpreter.get_tensor(input_details["index"])[0])
            # exit()
        num_correct += (np.argmax(np.array(output)) == t[id].item())
        # print(output)
    print("Accuracy:",num_correct/len(t))
    return interpreter, ti4, a1



class CMSISLayer:
    def __init__(self,weights,bias,in_scale,in_zp,out_scale,out_zp,multiplier,shift):
        self.weights = weights
        self.bias = bias
        self.in_scale = in_scale
        self.in_zp = in_zp
        self.out_scale = out_scale
        self.out_zp = out_zp
        self.multiplier = multiplier
        self.shift = shift

    @abstractmethod
    def forward(self,input):
        pass

class CMSISFCLayer(CMSISLayer):
    def __init__(self, weights, bias, in_scale, in_zp, out_scale, out_zp, multiplier, shift):
        super().__init__(weights, bias, in_scale, in_zp, out_scale, out_zp, multiplier, shift)
        # print(self.weights,self.bias)
        pass

    def forward(self, input):
        # forward
        activation = np.int32(np.array(input-self.in_zp))@np.int32(np.array(self.weights).T)+np.int32(np.array(self.bias))

        # requantize
        activation = (np.int64(activation)*np.int64(self.multiplier)) >> (31-self.shift)
        activation = np.clip(activation+self.out_zp,-128,127)

        return activation
    
class CMSISCONVLayer(CMSISLayer):
    def __init__(self, weights, bias, in_scale, in_zp, out_scale, out_zp, channel_multipliers, channel_shifts, padding_type,stride):
        super().__init__(weights, bias, in_scale, in_zp, out_scale, out_zp, None, None)
        self.channel_multipliers = channel_multipliers
        self.channel_shifts = channel_shifts
        self.padding = padding_type.lower()
        self.stride = stride

    def forward(self, input):
        # forward
        input = torch.tensor(np.int32(np.array(input-self.in_zp)))
        if len(input.shape) == 2:
            input.unsqueeze(0)
        weight = torch.tensor(np.int32(np.array(self.weights))).squeeze(1).permute(0,2,1)
        bias = torch.tensor(np.int32(np.array(self.bias).T))
        output = np.array(F.conv1d(input,weight,bias,self.stride,self.padding))

        # requantize
        for ch_i in range(output.shape[0]):
            out_ch = output[ch_i,:]
            act = (np.int64(out_ch)*np.int64(self.channel_multipliers[ch_i])) >> (31-self.channel_shifts[ch_i])
            output[ch_i,:] = np.clip(act+self.out_zp,-128,127)

        return output
    
#TODO: I know why the simulation doesn't work, the padding on the input layer is wrong I think
# or maybe its just the rounding issue because I don't dequantize exactly how arm does it
class CMSISNetwork:
    def __init__(self,cmsis_layer_list):
        self.cmsis_layer_list = cmsis_layer_list

    def test_model(self,test_inputs,expected_outputs,converter,verbose=False):
        idx = 0
        for inp,exp_out in zip(test_inputs,expected_outputs):
            out = inp
            for layer in self.cmsis_layer_list:
                out = layer.forward(out)
                if verbose == True:
                    print(out)
            # print(out,exp_out)

            try:
                if verbose:
                    print(out.flatten(),exp_out)
                np.testing.assert_allclose(out.flatten(), exp_out, atol=5)
            except Exception as e:
                print(e)
                print(f"{converter.BOLD}{converter.FAIL}Simulated CMSIS Model Behavior DOES NOT match with TFLITE (idx: {idx}/{len(test_inputs)}){converter.ENDC}")
                print(test_inputs[idx])
                exit()
            idx += 1

        print(f"{converter.BOLD}{converter.OKGREEN}Simulated CMSIS Model Behavior Matches with TFLITE{converter.ENDC}")



if __name__ == '__main__':
    root_dir = ["../acc_logs/wave.log",
            "../acc_logs/shake.log",
            "../acc_logs/clap.log",
            "../acc_logs/none.log"]
    train_loader, val_loader = load_gestures_nrf(0.75, 256, root_dir,window_len=25)
    m = Classifier(25)
    state_dict = torch.load("models/baseline.pth")['model_state_dict']
    m = m.to('cpu')
    m.load_state_dict(state_dict)
    sample_input = torch.rand((1, 75))

    mc = ModelConverter()
    mc.pytorch_to_onnx(m,sample_input)
    mc.onnx_to_tensorflow()
    
    sample_inputs, sample_outputs = mc.tensorflow_to_quantized_tflite(train_loader,val_loader,0.5)

    mc.tflite_to_cmsisnn(sample_inputs,sample_outputs)
    
    source_dir = 'TestCases/TestData/Classifier'
    target_dir = '../Classifier/'
    files = os.listdir(source_dir)
    for file in files:
        source_file = os.path.join(source_dir, file)
        destination_file = os.path.join(target_dir, file)
        shutil.copy(source_file, destination_file)
    

    exit()
   
    # convert_model(None)
    interpreter, inp, output_data = eval_model(None)

    # get input details
    input_details = interpreter.get_input_details()
    (input_scale, input_zero_point) = input_details[0]['quantization']

    # get parameter details
    all_layers_details = interpreter.get_tensor_details()
    filter_layer = all_layers_details[6]
    bias_layer = all_layers_details[5]
    act_layer = all_layers_details[7]

    # for l in all_layers_details:
    #     print(l)
    #     print()

    # print(act_layer)

    (output_scale1, output_zero_point1) = act_layer['quantization']

    weights_scale,weights_zp = filter_layer['quantization']
    bias_scale,bias_zp = bias_layer['quantization']

    # get the quant params
    input_product_scale = input_scale * weights_scale
    real_multipler = input_product_scale / output_scale1
    significand, shift = math.frexp(real_multipler)
    significand_q31 = round(significand * (1 << 31))
    quantized_multiplier, quantized_shift = significand_q31,shift
    print(f"shift: {quantized_shift}, multiplier: {quantized_multiplier}")

    # get the weight and bias
    weights = interpreter.get_tensor(filter_layer['index'])
    bias = interpreter.get_tensor(bias_layer['index'])

    # print(f"Input:{inp}")
    # print(f"a1:{a1}")

    # try to do the ops manually
    aq = np.int32(np.array(inp-input_zero_point))@np.int32(np.array(weights).T)+np.int32(np.array(bias))

    # print(aq)

    aq = (np.int64(aq)*np.int64(quantized_multiplier)) >> (31-quantized_shift)
    aq = np.clip(aq+output_zero_point1,-128,127)

    # print(f"manual:{aq}")

    
    # ===============

    # get parameter details
    filter_layer = all_layers_details[4]
    bias_layer = all_layers_details[3]
    act_layer = all_layers_details[8]

    (output_scale2, output_zero_point2) = act_layer['quantization']

    weights_scale,weights_zp = filter_layer['quantization']
    bias_scale,bias_zp = bias_layer['quantization']

    # get the quant params
    input_product_scale = output_scale1 * weights_scale
    real_multipler = input_product_scale / output_scale2
    significand, shift = math.frexp(real_multipler)
    significand_q31 = round(significand * (1 << 31))
    quantized_multiplier, quantized_shift = significand_q31,shift

    # get the weight and bias
    weights = interpreter.get_tensor(filter_layer['index'])
    bias = interpreter.get_tensor(bias_layer['index'])

    # try to do the ops manually
    aq = np.int32(np.array(aq-output_zero_point1))@np.int32(np.array(weights).T)+np.int32(np.array(bias))

    # print(aq)

    aq = (np.int64(aq)*np.int64(quantized_multiplier)) >> (31-quantized_shift)
    aq = np.clip(aq+output_zero_point2,-128,127)


    # ===============

    # get parameter details
    filter_layer = all_layers_details[2]
    bias_layer = all_layers_details[1]
    act_layer = all_layers_details[9]

    (output_scale3, output_zero_point3) = act_layer['quantization']

    weights_scale,weights_zp = filter_layer['quantization']
    bias_scale,bias_zp = bias_layer['quantization']

    # get the quant params
    input_product_scale = output_scale2 * weights_scale
    real_multipler = input_product_scale / output_scale3
    significand, shift = math.frexp(real_multipler)
    significand_q31 = round(significand * (1 << 31))
    quantized_multiplier, quantized_shift = significand_q31,shift

    # get the weight and bias
    weights = interpreter.get_tensor(filter_layer['index'])
    bias = interpreter.get_tensor(bias_layer['index'])

    # try to do the ops manually
    aq = np.int32(np.array(aq-output_zero_point2))@np.int32(np.array(weights).T)+np.int32(np.array(bias))

    aq = (np.int64(aq)*np.int64(quantized_multiplier)) >> (31-quantized_shift)
    aq = np.clip(aq+output_zero_point3,-128,127)

    print(f"tfl:{output_data}")
    print(f"manual:{aq}")
