from qiskit.circuit import QuantumCircuit
import torch
import qiskit as qk
from qiskit import QuantumCircuit
import torch.nn as nn
from qiskit_machine_learning.neural_networks import SamplerQNN
from torch_connector import TorchConnector
import torch.nn.functional as F
import time

# def get_result(job):
#     return job.result()


# class MyBackendSampler(BackendSampler):
#     def __init__(self, backend):
#         super().__init__(backend)
#     def _run(self, circuits: tuple[QuantumCircuit, ...], parameter_values: tuple[tuple[float, ...], ...], **run_options):
#         # super()._run(circuits, parameter_values, **run_options)
#         return super()._run(circuits, parameter_values, **run_options)

    


class Quanv2d(nn.Module):
    
    '''
        A quantum convolutional layer
--------------------------------------------
        args
            input_channel: number of input channels
            output_channel: number of output channels
            num_qubits: number of qubits
            num_weight: number of weights
            kernel_size: size of the kernel
            stride: stride of the kernel
    '''
    def __init__(self,
                 input_channel : int,
                 output_channel : int,
                 num_qubits : int,
                 num_weight : int, 
                 kernel_size : int = 3, 
                 stride : int = 1
                 ):

        super(Quanv2d, self).__init__()
        self.kernel_size = kernel_size
        self.stride = stride
        self.input_channel = input_channel
        self.output_channel = output_channel
        self.backend = qk.Aer.get_backend('qasm_simulator')
        # self.sampler = MyBackendSampler(backend=self.backend)
        self.qnn = TorchConnector(self.Sampler(num_weight,kernel_size * kernel_size * input_channel, num_qubits))
        # self.qnn = self.Sampler(num_weight,kernel_size * kernel_size * input_channel, num_qubits)
        #check if 2**num_qubits is greater than output_channel
        assert 2**num_qubits >= output_channel, '2**num_qubits must be greater than output_channel'

    def Sampler(self, 
                num_weights : int, 
                num_input : int, 
                num_qubits : int = 3
                ):
        '''
        build the quantum circuit
        param
            num_weights: number of weights
            num_input: number of inputs
            num_qubits: number of qubits
        return
            qc: quantum circuit
        '''
        qc = QuantumCircuit(num_qubits)
        weight_params = [qk.circuit.Parameter('w{}'.format(i)) for i in range(num_weights)]
        input_params = [qk.circuit.Parameter('x{}'.format(i)) for i in range(num_input)]
        #construct the quantum circuit with the parameters
        for i in range(num_qubits):
            qc.h(i)
        for i in range(num_input):
            qc.ry(input_params[i]*2*torch.pi, i%num_qubits)
        for i in range(num_qubits - 1):
            qc.cx(i, i + 1)
        for i in range(num_weights):
            qc.rx(weight_params[i]*2*torch.pi, i%num_qubits)
        for i in range(num_qubits - 1):
            qc.cx(i, i + 1)

        #use SamplerQNN to convert the quantum circuit to a PyTorch module
        qnn = SamplerQNN(
                        circuit = qc,
                        weight_params = weight_params,
                        interpret=self.interpret, 
                        input_params=input_params,
                        output_shape=self.output_channel,
                         )
        return qnn

    def interpret(self, X: int|list[int]) -> int|list[int]:
        '''
        interpret the output of the quantum circuit using the modulo function
        this function is used in SamplerQNN
        args
            X: output of the quantum circuit
        return
            the remainder of the output divided by the number of output channels
        '''
        return X%self.output_channel

    def forward(self, X : torch.Tensor) -> torch.Tensor:
        '''
        forward function for the quantum convolutional layer
        args
            X: input tensor with shape (batch_size, input_channel, height, width)
        return
            X: output tensor with shape (batch_size, output_channel, height, width)
        '''
        height = len(range(0,X.shape[2]-self.kernel_size+1,self.stride))
        width = len(range(0,X.shape[3]-self.kernel_size+1,self.stride))
        output = torch.zeros((X.shape[0],self.output_channel,height,width))
        X = F.unfold(X[:, :, :, :], kernel_size=self.kernel_size, stride=self.stride)
        qnn_output = self.qnn(X.permute(2, 0, 1)).permute(1, 2, 0)
        qnn_output = torch.reshape(qnn_output,shape=(X.shape[0],self.output_channel,height,width))
        output += qnn_output
        return output
 
if __name__ == '__main__':
    # Define the model
    model = Quanv2d(3, 2, 3, 5,stride=1)
    X = torch.rand((5,3,8,8))
    time0 = time.time()
    X1=model.forward(X)
    time1 = time.time()
    print(time1-time0)
    print(model)
    print(X1.shape)
    print(X1[0])
