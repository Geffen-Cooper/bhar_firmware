import torch
from torch import nn
import torch.quantization
from torch.quantization import QuantStub,DeQuantStub
import os
from dataset import *
from train import *
import torch.nn.functional as F

# ========================= Helper Functions =====================
def print_model_size(model):
    num_parameters = 0
    param_size = 0
    for param in model.parameters():
        num_parameters += param.nelement()
        param_size += param.nelement()*param.element_size()

    print("Number of parameters:", num_parameters)
    print("Model size (KB):",param_size/1e3)


activity_model = True
big_model = False

class Classifier(nn.Module):
    def __init__(self,window_len,num_classes=6):
        super().__init__()

        if activity_model == True:
            self.fc1 = nn.Linear(3*window_len,64)
            self.fc2 = nn.Linear(64,16)
            self.fc3 = nn.Linear(16,num_classes)
        elif big_model == True:
            self.fc1 = nn.Linear(30,128)
            self.fc2 = nn.Linear(128,128)
            self.fc3 = nn.Linear(128,128)
            self.fc4 = nn.Linear(128,128)
            self.fc5 = nn.Linear(128,128)
            self.fc6 = nn.Linear(128,128)
            self.fc7 = nn.Linear(128,128)
            self.fc8 = nn.Linear(128,8)
            self.fc9 = nn.Linear(8,4)

    def forward(self, x):
        if activity_model:
            # Layer 1
            x = F.relu(self.fc1(x))

            # Layer 2
            x = F.relu(self.fc2(x))

            # Layer 3
            x = self.fc3(x)

        elif big_model:
            # Layer 1
            x = F.relu(self.fc1(x))

            # ==================== #

            # Layer 2 (x1)
            x = F.relu(self.fc2(x))

            # Layer 3 (x2)
            x = F.relu(self.fc3(x))

            # Layer 4 (x3)
            x = F.relu(self.fc4(x))

            # Layer 5 (x4)
            x = F.relu(self.fc5(x))

            # Layer 6 (x5)
            x = F.relu(self.fc6(x))

            # Layer 7 (x6)
            x = F.relu(self.fc7(x))

            # ==================== #

            # Layer 8
            x = F.relu(self.fc8(x))

            # Layer 9
            x = self.fc9(x)

        return x
    

class VanillaCNN(nn.Module):
    def __init__(self,in_channels, output_classes):
        super().__init__()

        self.conv1 = nn.Conv1d(in_channels, 16, 5)
        self.conv2 = nn.Conv1d(16, 16, 5)
        self.conv3 = nn.Conv1d(16, 16, 5)
        self.conv4 = nn.Conv1d(16, 16, 5)
        self.conv5 = nn.Conv1d(16, 16, 5)
        self.conv6 = nn.Conv1d(16, 16, 5)
        self.conv7 = nn.Conv1d(16,7,1)
    

    def forward(self, x, depth=None):
        # (3 x 25) --> (16 x 21)
        x = F.relu(self.conv1(x))

        # (16 x 21) --> (16 x 17)
        x = F.relu(self.conv2(x))

        # (16 x 17) --> (16 x 13)
        x = F.relu(self.conv3(x))

        # (16 x 13) --> (16 x 9)
        x = F.relu(self.conv4(x))

        # (16 x 9) --> (16 x 5)
        x = F.relu(self.conv5(x))

        # (16 x 5) --> (16 x 1)
        x = F.relu(self.conv6(x))

        # (16 x 1) --> (num classes)
        x = self.conv7(x)

        return x
    

if __name__ == '__main__':
    m = VanillaCNN(3,7)
    print(m)
    x = torch.randn(1,3,25)
    print(m(x).shape)
    # print_model_size(m)
    # print(m.conv1.bias)