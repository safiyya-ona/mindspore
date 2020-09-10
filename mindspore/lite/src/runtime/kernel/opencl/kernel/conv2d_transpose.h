/**
 * Copyright 2019 Huawei Technologies Co., Ltd
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef MINDSPORE_LITE_SRC_RUNTIME_KERNEL_OPENCL_KERNEL_CONV2D_TRANSPOSE_H_
#define MINDSPORE_LITE_SRC_RUNTIME_KERNEL_OPENCL_KERNEL_CONV2D_TRANSPOSE_H_

#include <vector>

#include "src/lite_kernel.h"
#include "nnacl/conv_parameter.h"
#include "src/runtime/opencl/opencl_runtime.h"
#include "src/runtime/kernel/opencl/opencl_kernel.h"

namespace mindspore::kernel {

class Conv2dTransposeOpenCLKernel : public OpenCLKernel {
 public:
  explicit Conv2dTransposeOpenCLKernel(OpParameter *parameter, const std::vector<lite::Tensor *> &inputs,
                                       const std::vector<lite::Tensor *> &outputs)
      : OpenCLKernel(parameter, inputs, outputs) {}
  ~Conv2dTransposeOpenCLKernel() override{};

  int Init() override;
  int ReSize() override;
  int Run() override;
  void PadWeight();
  int GetImageSize(size_t idx, std::vector<size_t> *img_size) override;

 private:
  cl::Kernel kernel_;
  void *padWeight_;
  void *bias_;
  bool enable_fp16_{false};
};
}  // namespace mindspore::kernel

#endif  // MINDSPORE_LITE_SRC_RUNTIME_KERNEL_OPENCL_KERNEL_CONV2D_TRANSPOSE_H_
