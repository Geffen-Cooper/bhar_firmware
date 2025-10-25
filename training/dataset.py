import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import re
import matplotlib as mpl
import os

def read_data_from_file(file_path,class_name):
    # Extract X, Y, and Z values
    X_values = []
    Y_values = []
    Z_values = []

    # re pattern to extract values from log
    pattern = r'X:\s*(-?\d+),\s*Y:\s*(-?\d+),\s*Z:\s*(-?\d+)'

    # Read the log file
    with open(file_path, 'r') as log_file:
        for line in log_file:
            match = re.search(pattern, line)
            if match:
                X_values.append(int(match.group(1)))
                Y_values.append(int(match.group(2)))
                Z_values.append(int(match.group(3)))

    # Convert lists to numpy arrays
    X_array = (np.array(X_values)/1024)*9.8
    Y_array = (np.array(Y_values)/1024)*9.8
    Z_array = (np.array(Z_values)/1024)*9.8
    t = np.arange(len(X_array))/25

    fig,ax = plt.subplots(1,1)
    ax.plot(t,X_array,label='X')
    ax.plot(t,Y_array,label='Y')
    ax.plot(t,Z_array,label='Z')
    ax.grid()
    ax.legend()
    ax.set_title(class_name)
    fig.savefig(f'{class_name}.png')
    # plt.show()
    plt.close()

    return X_array, Y_array, Z_array


class GestureDatasetNRF(Dataset):
    def __init__(self, log_files,window_len=50):
        self.samples = []
        self.labels = []
        self.window_len = window_len
        self.class_names = ["Wave","Shake","Clap","None"]
        self.class_map = {i:self.class_names[i] for i in range(len(self.class_names))}
        
        
        for class_idx,log_file in enumerate(log_files):
            x_array, y_array, z_array = read_data_from_file(log_file,self.class_map[class_idx])

            # each sample is a tuple of an (x,y,z) window
            possible_samples = len(x_array)-window_len+1
            for sample_idx in range(possible_samples):
                s = sample_idx
                e = sample_idx+window_len
                self.samples.append((x_array[s:e],y_array[s:e],z_array[s:e]))
                # print(self.labels)
                self.labels.append(class_idx)


        # filter out good samples (i.e. remove the end points)
        self.labels = np.array(self.labels)
        self.good_idxs = np.concatenate([(self.labels == i).nonzero()[0][window_len:-window_len] for i in range(len(self.class_names))])

        self.accelerometer_vals = []
        # now convert the samples to flat vectors
        for sample in self.samples:
            x,y,z = sample
            self.accelerometer_vals.append(np.concatenate([x,y,z]))

        self.accelerometer_vals = np.stack(self.accelerometer_vals)

        mean = self.accelerometer_vals.mean()
        std = self.accelerometer_vals.std()
        self.accelerometer_vals = (self.accelerometer_vals-mean)/(std+1e-5)
        print(f'mean: {mean}, std: {std}')

    def __len__(self):
        # return len(self.labels)
        return len(self.good_idxs)


    def __getitem__(self, idx):
        idx = self.good_idxs[idx]
        # shift to range [-128,127], clip numbers outside this range, divide by 128 to normalize
        # ideally we should find the shift amount that gets the highest percent into the range and clip the rest
        label = self.labels[idx]
        accelerometer_data = self.accelerometer_vals[idx].astype(float)#/128

        return torch.tensor(accelerometer_data), torch.tensor(label,dtype=torch.long)

    def visualize_samples(self):
        matplotlib.rcParams.update({'font.size': 6})
        idxs = torch.randperm(len(self))[:16]
        fig,ax = plt.subplots(4,4,figsize=(9,5))
        fig.subplots_adjust(wspace=0.6,hspace=1)
        for i,idx in enumerate(idxs):
            accelerometer_data,l = self.__getitem__(idx)
            x = accelerometer_data[:self.window_len]
            y = accelerometer_data[self.window_len:2*self.window_len]
            z = accelerometer_data[2*self.window_len:]

            i_x = i % 4
            i_y = i // 4
            x_ = np.arange(self.window_len)
            ax[i_y,i_x].plot(x_,x,label='X')
            ax[i_y,i_x].plot(x_,y,label='Y')
            ax[i_y,i_x].plot(x_,z,label='Z')
            ax[i_y,i_x].set_xlabel("Sample #")
            ax[i_y,i_x].set_ylabel("Value")
            ax[i_y,i_x].set_title(self.class_map[int(l)])
            # ax[i_y,i_x].legend(loc=(1.05,0.3))

        # print(self.max)
        plt.savefig("viz.png")
        plt.show()


def load_gestures_nrf(train_frac,batch_size,log_files,window_len=50):
    dataset = GestureDatasetNRF(log_files,window_len=window_len)
    # print("----------")
    print(len(dataset))
    train_len = int(len(dataset)*train_frac)
    train_split,val_split = torch.utils.data.random_split(dataset,[train_len,len(dataset)-train_len],
                                                          generator=torch.Generator().manual_seed(0))

    train_loader = DataLoader(train_split,batch_size,shuffle=True)
    val_loader = DataLoader(val_split,batch_size)
    
    return train_loader, val_loader


if __name__ == '__main__':
    
    logs = ["../acc_logs/wave.log",
            "../acc_logs/shake.log",
            "../acc_logs/clap.log",
            "../acc_logs/none.log"]
    dataset = GestureDatasetNRF(logs,window_len=25)
    dataset.visualize_samples()
    load_gestures_nrf(0.75,16,logs,25)
    # print(dataset[10][0].shape)

        