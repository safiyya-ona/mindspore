import numpy as np
from mindspore import context
import mindspore as ms
import mindspore.nn as nn
from mindspore.nn.optim import Adam, FTRL
from mindspore.ops import operations as P
from mindspore.ops import functional as F
from mindspore import Tensor, Parameter, ParameterTuple
from mindspore.ops import composite as C
from mindspore.parallel import _cost_model_context as cost_model_context
from mindspore.common.api import _executor
from mindspore.parallel import set_algo_parameters, get_algo_parameters, reset_algo_parameters
from mindspore.parallel._utils import _reset_op_id as reset_op_id

class Net(nn.Cell):
    def __init__(self):
        super(Net, self).__init__()
        self.mul = P.Mul()
        self.relu = P.ReLU()
        self.wd = Parameter(Tensor(np.ones([8, 8, 8, 8]).astype(np.float32)), name="wide")
        self.wt = Parameter(Tensor(np.ones([8, 8, 8, 8]).astype(np.float32)), name="l")
    def construct(self, x):
        out = self.mul(x, self.wd)
        out = self.mul(out, self.wt)
        out = self.relu(out)
        return out

class NetWithLoss(nn.Cell):
    def __init__(self, network):
        super(NetWithLoss, self).__init__()
        self.sum = P.ReduceSum()
        self.mean = P.ReduceMean()
        self.net = network

    def construct(self, x):
        predict = self.net(x)
        loss1 = self.sum(predict, -1)
        loss2 = self.mean(predict, -1)
        return loss1, loss2

class IthOutputCell(nn.Cell):
    def __init__(self, network, output_index):
        super(IthOutputCell, self).__init__()
        self.network = network
        self.output_index = output_index

    def construct(self, x):
        predict = self.network(x)[self.output_index]
        return predict

class TrainStepWarp(nn.Cell):
    def __init__(self, network, sens=1000.0):
        super(TrainStepWarp, self).__init__()
        self.network = network
        self.network.set_train()
        self.trainable_params = network.trainable_params()
        weights_w = []
        weights_d = []
        for params in self.trainable_params:
            weights_w.append(params)
            weights_d.append(params)
        self.weights_w = ParameterTuple(weights_w)
        self.weights_d = ParameterTuple(weights_d)
        self.optimizer_w = FTRL(learning_rate=1e-2, params=self.weights_w, l1=1e-8,
                                l2=1e-8, initial_accum=1.0)
        self.optimizer_d = Adam(self.weights_d, learning_rate=3.5e-4, eps=1e-8,
                                loss_scale=sens)
        self.hyper_map = C.HyperMap()
        self.grad_w = C.GradOperation('grad_w', get_by_list=True, sens_param=True)
        self.grad_d = C.GradOperation('grad_d', get_by_list=True, sens_param=True)
        self.sens = sens
        self.loss_net_w = IthOutputCell(network, output_index=0)
        self.loss_net_d = IthOutputCell(network, output_index=1)

    def construct(self, x):
        weights_w = self.weights_w
        weights_d = self.weights_d
        loss_w, loss_d = self.network(x)
        sens_w = P.Fill()(P.DType()(loss_w), P.Shape()(loss_w), self.sens)
        sens_d = P.Fill()(P.DType()(loss_d), P.Shape()(loss_d), self.sens)
        grads_w = self.grad_w(self.loss_net_w, weights_w)(x, sens_w)
        grads_d = self.grad_d(self.loss_net_d, weights_d)(x, sens_d)
        return F.depend(loss_w, self.optimizer_w(grads_w)), F.depend(loss_d, self.optimizer_d(grads_d))

def test_double_subgraphs():
    cost_model_context.set_cost_model_context(multi_subgraphs=True)
    context.set_context(save_graphs=True)
    context.set_auto_parallel_context(device_num=8, global_rank=0)
    net = TrainStepWarp(NetWithLoss(Net()))
    context.set_auto_parallel_context(parallel_mode="auto_parallel")
    net.set_auto_parallel()

    x = Tensor(np.ones([8, 8, 8, 8]), dtype=ms.float32)
    reset_op_id()
    _executor.compile(net, x, phase='train')
    strategies = _executor._get_strategy(net)
    expected_strategies = {'Default/network-NetWithLoss/ReduceMean-op0': [[8, 1, 1, 1]],
                           'Default/network-NetWithLoss/net-Net/ReLU-op1': [[8, 1, 1, 1]],
                           'Default/network-NetWithLoss/net-Net/Mul-op2': [[8, 1, 1, 1], [8, 1, 1, 1]],
                           'Default/network-NetWithLoss/net-Net/Mul-op3': [[8, 1, 1, 1], [8, 1, 1, 1]],
                           'Default/network-NetWithLoss/ReduceSum-op4': [[8, 1, 1, 1]]}
    assert strategies == expected_strategies
