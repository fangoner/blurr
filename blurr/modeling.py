# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02_modeling.ipynb (unless otherwise specified).

__all__ = ['hf_splitter', 'HF_BaseModelCallback', 'HF_BaseModelWrapper', 'HF_QstAndAnsModelCallback',
           'HF_QstAndAnsModelWrapper', 'MultiTargetLoss']

# Cell
from .utils import *
from .data import *

import torch
from transformers import *
from fastai2.text.all import *

# Cell
def hf_splitter(m):
    """Splits the huggingface model based on various model architecture conventions"""
    model = m.hf_model if (hasattr(m, 'hf_model')) else m
    root_modules = list(model.named_children())
    top_module_name, top_module = root_modules[0]

    groups = L([ m for m_name, m in list(top_module.named_children()) ])
    groups += L([ m for m_name, m in root_modules[1:] ])

    return groups.map(params).filter(lambda el: len(el) > 0)

# Cell
class HF_BaseModelCallback(Callback):

    def begin_fit(self):
        self.hf_model = self.model
        self.hf_model_fwd_args = self.model.forward.__code__.co_varnames

    def begin_batch(self):
        x = self.xb[0]
        model_args = [x[0]]
        if (self._include_arg('attention_mask', x[2])): model_args.append(x[2])
        if (self._include_arg('token_type_ids', x[1])): model_args.append(x[1])

        self.learn.xb = tuplify(model_args)

    def after_pred(self):
        self.learn.pred = self.pred[0]

    def _include_arg(self, arg_name, tensor_val):
        if (tensor_val[0][0].item() == -9999 or arg_name not in self.hf_model_fwd_args):
            return False
        return True

# Cell
class HF_BaseModelWrapper(Module):
    def __init__(self, hf_model):
        super().__init__()
        self.hf_model = hf_model
        self.hf_model_fwd_args = hf_model.forward.__code__.co_varnames

    def forward(self, x):
        model_kwargs = {}
        model_kwargs['input_ids'] = x[0]
        if (self._include_arg('token_type_ids', x[1])): model_kwargs['token_type_ids'] = x[1]
        if (self._include_arg('attention_mask', x[2])): model_kwargs['attention_mask'] = x[2]

        outputs = self.hf_model(**model_kwargs)
        return outputs[0]

    def _include_arg(self, arg_name, tensor_val):
        if (tensor_val[0][0].item() == -9999 or arg_name not in self.hf_model_fwd_args):
            return False
        return True

# Cell
@typedispatch
def show_results(x:HF_BaseInput, y, samples, outs, hf_tokenizer, ctxs=None, max_n=6, **kwargs):
    if ctxs is None: ctxs = get_empty_df(min(len(samples), max_n))

    samples = samples = L((TitledStr(hf_tokenizer.decode(inp)),*s[1:]) for inp, s in zip(x[0], samples))
    ctxs = show_batch[object](x, y, samples, max_n=max_n, ctxs=ctxs, **kwargs)

    n_preds_per_input = len(outs[0])
    if (n_preds_per_input == 1):
        for i,ctx in enumerate(ctxs): ctx['target'] = outs[i][0]
    else:
        for pred_idx in range(n_preds_per_input):
            for i,ctx in enumerate(ctxs):  ctx[f'target{pred_idx+1}'] = outs[i][pred_idx]

    display_df(pd.DataFrame(ctxs))
    return ctxs

# Cell
class HF_QstAndAnsModelCallback(HF_BaseModelCallback):
    def after_pred(self):
        self.learn.pred = self.pred

# Cell
class HF_QstAndAnsModelWrapper(HF_BaseModelWrapper):
    """A custom model wrapper for question answer models since we need all the outputs (not just the first)"""
    def forward(self, x):
        model_kwargs = {}
        model_kwargs['input_ids'] = x[0]
        if (self._include_arg('token_type_ids', x[1])): model_kwargs['token_type_ids'] = x[1]
        if (self._include_arg('attention_mask', x[2])): model_kwargs['attention_mask'] = x[2]

        outputs = self.hf_model(**model_kwargs)
        return outputs

# Cell
class MultiTargetLoss(Module):
    """Provides the ability to apply different loss functions to multi-modal targets/predictions"""
    def __init__(self, funcs=[F.cross_entropy, F.cross_entropy],
                 func_kwargs=[{}, {}],
                 weights=[1, 1],
                 activation_funcs=[partial(F.softmax, dim=-1), partial(F.softmax, dim=-1)],
                 decode_funcs =[partial(torch.argmax, dim=-1), partial(torch.argmax, dim=-1)],
                 reduction='mean'):

        store_attr(self, 'funcs, func_kwargs, weights, activation_funcs, decode_funcs, reduction')

    def forward(self, outputs, *targets):
        for i, func, func_kwargs, weights, output, target in zip(range(len(outputs)),
                                                                 self.funcs, self.func_kwargs, self.weights,
                                                                 outputs, targets):

            if i == 0:
                loss = weights * func(output, target, reduction=self.reduction, **func_kwargs)
            else:
                loss += weights * func(output, target, reduction=self.reduction, **func_kwargs)

        return loss

    def activation(self, outs):
        acts = [ self.activation_funcs[i](o) for i, o in enumerate(outs) ]
        return acts

    def decodes(self, outs):
        decodes = [ self.decode_funcs[i](o) for i, o in enumerate(outs) ]
        return decodes
