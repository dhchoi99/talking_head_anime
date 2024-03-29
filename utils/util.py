import contextlib
import importlib
import os
import shutil

import torch
from torch.utils.data import DataLoader


def suppress_stdout(func):
    def wrapper(*a, **ka):
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                return func(*a, **ka)

    return wrapper


def save_files(path_save, savefiles):
    os.makedirs(path_save, exist_ok=True)
    for savefile in savefiles:
        path_split = os.path.normpath(savefile).split(os.sep)
        if len(path_split) >= 2:
            dir = os.path.join(path_save, *path_split[:-1])
            os.makedirs(dir, exist_ok=True)
        try:
            shutil.copy2(savefile, os.path.join(path_save, savefile))
        except Exception as e:
            print(f'{e} occured while saving {savefile}')


def cycle(iterable):
    iterator = iter(iterable)
    while True:
        try:
            yield next(iterator)
        except StopIteration:
            iterator = iter(iterable)


def build_datasets_from_config(conf, build_loaders=True, build_iterators=True):
    # Dataset and Dataloader setup
    datasets = {}
    loaders = {}
    iterators = {}
    for key, conf_dataset in conf.items():
        module, cls = conf_dataset['class'].rsplit(".", 1)
        D = getattr(importlib.import_module(module, package=None), cls)
        datasets[key] = D(conf_dataset)
        if build_loaders:
            loaders[key] = DataLoader(
                datasets[key], batch_size=conf_dataset.batch_size,
                shuffle=conf_dataset.shuffle, drop_last=True,
                num_workers=conf_dataset.num_workers
            )
        if build_iterators:
            iterators[key] = cycle(loaders[key])
    return datasets, loaders, iterators


def load_checkpoint(model, path):
    data = torch.load(path, map_location='cpu')
    device = model.device

    model = model.to('cpu')
    model.load_state_dict(data)
    model = model.to(device)
    return model


def build_models_from_config(conf, build_optims=True):
    models = {}
    optims = {}

    for model_key, model_conf in conf.items():
        module, cls = model_conf['class'].rsplit('.', 1)
        M = getattr(importlib.import_module(module, package=None), cls)
        m = M(model_conf)

        if 'ckpt' in model_conf.keys() and os.path.isfile(model_conf['ckpt']):
            m = load_checkpoint(m, model_conf['ckpt'])

        models[model_key] = m

        if build_optims and 'optim' in model_conf.keys():
            conf_optim = model_conf['optim']
            optim_module, optim_cls = conf_optim['class'].rsplit(".", 1)
            O = getattr(importlib.import_module(optim_module, package=None), optim_cls)
            o = O([p for p in models[model_key].parameters() if p.requires_grad],
                  **conf_optim.kwargs)

            if 'ckpt' in conf_optim.keys() and os.path.isfile(conf_optim['ckpt']):
                o = load_checkpoint(o, conf_optim['ckpt'])
            optims[model_key] = o

    return models, optims
