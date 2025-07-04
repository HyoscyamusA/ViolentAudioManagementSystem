# Copyright 2017 The TensorFlow Authors All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""
Compute input examples for VGGish from audio waveform.
从音频波形计算VGGish的输入事例
"""

import numpy as np
import resampy

import mel_features
import vggish_params

try:
  import soundfile as sf

  def wav_read(wav_file):
    wav_data, sr = sf.read(wav_file, dtype='int16')
    return wav_data, sr

except ImportError:

  def wav_read(wav_file):
    raise NotImplementedError('WAV file reading requires soundfile package.')
#读取WAV文件需要 soundfile包
#----------------------------------------------------------------------------------------------------
def waveform_to_examples(data, sample_rate):
  """Converts audio waveform into an array of examples for VGGish.
    将音频波形转换为VGGish输入事例的数组
  Args:
    1 data: np.array of either one dimension (mono) or two dimensions
      (multi-channel, with the outer dimension representing channels).
      Each sample is generally expected to lie in the range [-1.0, +1.0],
      although this is not required.
    2 sample_rate: Sample rate of data.
  参数：有两个
        data: np.array,包含一维（单声道）或二维（多声道，外维表示声道）数据。
              每个样本通常在 [-1.0, +1.0] 范围内，但这并不是强制要求。
        sample_rate: 音频数据的采样率。

  Returns:
    3-D np.array of shape [num_examples, num_frames, num_bands] which represents
    a sequence of examples, each of which contains a patch of log mel
    spectrogram, covering num_frames frames of audio and num_bands mel frequency
    bands, where the frame length is vggish_params.STFT_HOP_LENGTH_SECONDS.
  返回：
    3D np.array，形状为 [num_examples, num_frames, num_bands]，表示一系列示例，
    每个示例包含一个 log mel 频谱图的片段，覆盖 num_frames 帧音频和 num_bands
    个 mel 频率带，其中帧长度为 vggish_params.STFT_HOP_LENGTH_SECONDS。
  """


  # Convert to mono.转换为单声道
  if len(data.shape) > 1:
    data = np.mean(data, axis=1)
  # Resample to the rate assumed by VGGish.
  #重采样到VGGish假定的采样率
  if sample_rate != vggish_params.SAMPLE_RATE:
    data = resampy.resample(data, sample_rate, vggish_params.SAMPLE_RATE)

  # Compute log mel spectrogram features.
  #计算log mel频谱图特征,在此计算VGGish模型输入所需要的特征
  log_mel = mel_features.log_mel_spectrogram(
      data,
      audio_sample_rate=vggish_params.SAMPLE_RATE,
      log_offset=vggish_params.LOG_OFFSET,
      window_length_secs=vggish_params.STFT_WINDOW_LENGTH_SECONDS,
      hop_length_secs=vggish_params.STFT_HOP_LENGTH_SECONDS,
      num_mel_bins=vggish_params.NUM_MEL_BINS,
      lower_edge_hertz=vggish_params.MEL_MIN_HZ,
      upper_edge_hertz=vggish_params.MEL_MAX_HZ)

  # Frame features into examples.
  #将特征分帧成实例
  features_sample_rate = 1.0 / vggish_params.STFT_HOP_LENGTH_SECONDS
  example_window_length = int(round(
      vggish_params.EXAMPLE_WINDOW_SECONDS * features_sample_rate))
  example_hop_length = int(round(
      vggish_params.EXAMPLE_HOP_SECONDS * features_sample_rate))
  log_mel_examples = mel_features.frame(
      log_mel,
      window_length=example_window_length,
      hop_length=example_hop_length)
  return log_mel_examples
#-------------------------------------------------------------------------------------------------------------

def wavfile_to_examples(wav_file):
  """Convenience wrapper around waveform_to_examples() for a common WAV format.
      封装waveform_to_examples()以处理常见的WAV格式
  Args参数:
    wav_file: String path to a file, or a file-like object. The file
    is assumed to contain WAV audio data with signed 16-bit PCM samples.
    wav_file:字符串形式的文件路径，或类似文件的对象。文件假定包含带有
    16位PCM样本的WAV音频数据
  Returns:
    See waveform_to_examples.

  """
  wav_data, sr = wav_read(wav_file)
  assert wav_data.dtype == np.int16, 'Bad sample type: %r' % wav_data.dtype
  samples = wav_data / 32768.0  # Convert to [-1.0, +1.0]
  return waveform_to_examples(samples, sr)
