import argparse
import glob
import math
import random
import re
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import matplotlib.pyplot as plt
import numpy as np
import time
from dataset import *
from model import *
import time


np.set_printoptions(linewidth=np.nan)


def train(loss,optimizer,log_name,root_dir,batch_size,epochs,ese,lr,use_cuda,seed,save_model_ckpt,window_len):

    # log training parameters
    print("===========================================")
    for k,v in zip(locals().keys(),locals().values()):
        print(f"locals/{k}", f"{v}")
    print("===========================================")

    # ================== parse the arguments ==================
    # torch.manual_seed(seed)
    # np.random.seed(seed)
    # random.seed(seed)

    # setup device
    use_cuda = use_cuda and torch.cuda.is_available()
    if use_cuda:
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    # set loss function
    if loss == "CE":
        loss_fn = torch.nn.CrossEntropyLoss()


    # ================== training loop ==================

    # how many epochs the validation loss did not decrease, 
    # used for early stopping
    val_accs = []
    train_losses = []
    val_losses = []
    val_accuracies = []
    val_idxs = []
    batch_iter = 0

    # model = Classifier()
    
    model = Classifier(window_len)

    model.train()
    model = model.to(device)
    checkpoint_path = 'models/' + log_name + ".pth"
    best_val_acc = 0
    lowest_loss = 1e6
    # set optimizer
    if optimizer == "SGD":
        opt = torch.optim.SGD(params=model.parameters(), lr=lr,momentum=0.9,weight_decay=1e-4)
    elif optimizer == "Adam":
        opt = torch.optim.Adam(params=model.parameters(), lr=lr)
    elif optimizer == "AdamW":
        opt = torch.optim.AdamW(params=model.parameters(), lr=lr)
    else:
        raise NotImplementedError()
    # load datasets
    # train_loader, val_loader = load_gestures_nrf(0.75, batch_size, root_dir,conv=False,window_len=10,_25hz=False)
    train_loader, val_loader = load_gestures_nrf(0.75, batch_size, root_dir,window_len=25)
    print("train")
    num_epochs_worse = 0
    for e in range(epochs):
        if num_epochs_worse == ese:
            break
        for batch_idx, (data, target) in enumerate(train_loader):
            # stop training, run on the test set
            if num_epochs_worse == ese:
                break

            data, target = data.to(device), target.to(device)

            opt.zero_grad()
            model.train()

            try:
                output = model(data.float())
            except:
                torch.save({
                'epoch': e + 1,
                'model_state_dict': model.state_dict()
                }, checkpoint_path)
                exit()

            train_loss = loss_fn(output, target)
            train_loss.backward()
            # print(train_loss)
            # print(model.fc2.weight.grad)
            # print(model.fc1.weight.grad)
            # exit()
            opt.step()
            train_losses.append(train_loss.detach().item())

            print('Train Epoch: {} [{}/{} ({:.0f}%)] train loss: {:.3f}'.format(
                e, batch_idx * train_loader.batch_size + len(data), len(train_loader.dataset),
                    100.0 * batch_idx / len(train_loader), train_loss))
            batch_iter += 1

        if num_epochs_worse == ese:
            print(f"Stopping training because accuracy did not improve after {num_epochs_worse} epochs")
            break

        # evaluate on the validation set
        val_acc, val_loss = validate(model, val_loader, device, loss_fn)
        val_losses.append(val_loss.cpu())
        val_accuracies.append(val_acc.cpu())
        val_idxs.append(batch_iter)

        print('Train Epoch: {} [{}/{} ({:.0f}%)] train loss: {:.3f}, val acc: {:.3f}, val loss: {:.3f}'.format(
            e, batch_idx * train_loader.batch_size + len(data), len(train_loader.dataset),
            100. * batch_idx / len(train_loader), train_loss, val_acc, val_loss))

        if best_val_acc < val_acc:
        # if lowest_loss > val_loss:
            print("==================== best validation metric ====================")
            print("epoch: {}, val acc: {}, val loss: {}".format(e, val_acc, val_loss))
            best_val_acc = val_acc
            lowest_loss = val_loss
            torch.save({
                'epoch': e + 1,
                'model_state_dict': model.state_dict(),
                'val_acc': val_acc,
                'val_loss': val_loss,
            }, checkpoint_path)
            num_epochs_worse = 0
        else:
            print(f"WARNING: {num_epochs_worse} num epochs without improving")
            num_epochs_worse += 1

    # evaluate on test set
    print(f"Best acc: {best_val_acc}")
    val_accs.append(best_val_acc)
    model = Classifier(window_len)
    state_dict = torch.load("models/baseline.pth")['model_state_dict']
    model.load_state_dict(state_dict)
    _, _ = validate(model, val_loader, device, loss_fn, True)

    print("========================= Training Finished =========================")
    
    for i,v in enumerate(val_accs):
        print(f"best acc: {v}")
    print(f"avg: {sum(val_accs)/len(val_accs)}")

    fig,ax = plt.subplots(1,2)
    ax[0].plot(np.arange(len(train_losses)),train_losses,label="Training Loss")
    ax[0].plot(val_idxs,val_losses,label="Validation Loss")
    ax[0].set_ylabel("Loss")
    ax[0].set_xlabel("Batch Iteration")
    ax[0].legend()
    ax[1].set_xlabel("Epoch")
    ax[1].set_ylabel("Accuracy")
    ax[1].plot(np.arange(len(val_accuracies)),val_accuracies,label="Validation Accuracy")
    ax[1].legend()
    plt.savefig("loss_curve.png")
    plt.show()


def validate(model, val_loader, device, loss_fn,prec=False):
    model.eval()
    model = model.to(device)

    val_loss = 0
    val_acc = 0
    with torch.no_grad():
        if prec == True:
            class_precs = torch.zeros(len(val_loader.dataset.dataset.class_names))
            class_lens = torch.zeros(len(val_loader.dataset.dataset.class_names))
            for idx, (data, target) in enumerate(val_loader):
                data, target = data.to(device), target.to(device)
                out = model(data.float())
                for i,c in enumerate(class_precs):
                    c_idxs = (target == i).nonzero().view(-1)
                    # print(torch.argmax(out[c_idxs],dim=1),target[c_idxs])
                    class_precs[i] += (torch.argmax(out[c_idxs],dim=1).cpu() == target[c_idxs].cpu()).float().sum()
                    class_lens[i] += len(c_idxs)

            for i,c in enumerate(class_precs):
                name = val_loader.dataset.dataset.class_names[i]
                print(f"class {name}: {class_precs[i]}/{class_lens[i]}")
            return None, None

        else:
            num_samples = 0
            for idx, (data, target) in enumerate(val_loader):
                data, target = data.to(device), target.to(device)
                out = model(data.float())
                val_loss += loss_fn(out, target)
                val_acc += (torch.argmax(out,dim=1) == target).float().sum()
                num_samples += len(target)
            
            print(f"{val_acc}/{num_samples}")
            # Compute loss and accuracy
            val_loss /= (len(val_loader))
            val_acc /= (num_samples)
            

        return val_acc, val_loss

# ===================================== Main =====================================
if __name__ == "__main__":

    # train_params = {'loss': "CE", 'optimizer': "SGD", 'log_name': "baseline", 'root_dir': "putty.log",
    #                 'batch_size': 8, 'epochs': 100, 'ese': 25, 'lr': 0.05, 'use_cuda': True, 'seed': 42,'save_model_ckpt': True,
    #                 'folds':1}

    logs = ["../acc_logs/wave.log",
            "../acc_logs/shake.log",
            "../acc_logs/clap.log",
            "../acc_logs/none.log"]
    train_params = {'loss': "CE", 'optimizer': "Adam", 'log_name': "baseline", 'root_dir': logs,'batch_size': 32, 'epochs': 300, 'ese': 5, 'lr': 0.001, 'use_cuda': False,
                    'seed': 42,'save_model_ckpt': True,'window_len':25}

    train(**train_params)

