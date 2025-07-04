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
Defines routines to compute mel spectrogram features from audio waveform.
定义从音频波形计算mel频谱特征的历程
"""

import numpy as np


def frame(data, window_length, hop_length):
  """Convert array into a sequence of successive possibly overlapping frames.
      将数组转换为一系列连续且可能重叠的帧
  
  An n-dimensional array of shape (num_samples, ...) is converted into an
  (n+1)-D array of shape (num_frames, window_length, ...), where each frame
  starts hop_length points after the preceding one.
  形状为 (num_samples, ...) 的 n 维数组将被转换为形状为 
  (num_frames, window_length, ...) 的 (n+1)-D 数组，其中每一帧
  在前一帧之后以 hop_length 点开始。

  This is accomplished using stride_tricks, so the original data is not
  copied.  However, there is no zero-padding, so any incomplete frames at the
  end are not included.
  这是通过 stride_tricks 实现的，因此原始数据不会被复制。
  然而，不进行零填充，因此任何不完整的帧都不会被包含在内。

  Args参数:
    data: np.array of dimension N >= 1.
    window_length: Number of samples in each frame.
    hop_length: Advance (in samples) between each window.
    
    data: N >= 1 维的 np.array。
    window_length: 每帧中的样本数量。
    hop_length: 每个窗口之间的推进步长（以样本数表示）。

  Returns:
    (N+1)-D np.array with as many rows as there are complete frames that can be
    extracted.
    (N+1) 维 np.array，包含可以提取的完整帧的行数。
  """
  num_samples = data.shape[0]
  num_frames = 1 + int(np.floor((num_samples - window_length) / hop_length))
  shape = (num_frames, window_length) + data.shape[1:]
  strides = (data.strides[0] * hop_length,) + data.strides
  return np.lib.stride_tricks.as_strided(data, shape=shape, strides=strides)


def periodic_hann(window_length):
  """Calculate a "periodic" Hann window.
    计算“周期性” Hann 窗口。

  The classic Hann window is defined as a raised cosine that starts and
  ends on zero, and where every value appears twice, except the middle
  point for an odd-length window.  Matlab calls this a "symmetric" window
  and np.hanning() returns it.  However, for Fourier analysis, this
  actually represents just over one cycle of a period N-1 cosine, and
  thus is not compactly expressed on a length-N Fourier basis.  Instead,
  it's better to use a raised cosine that ends just before the final
  zero value - i.e. a complete cycle of a period-N cosine.  Matlab
  calls this a "periodic" window. This routine calculates it.
  经典的 Hann 窗口是一个以零开始和结束的升余弦，其中每个值出现两次，
  除了奇数长度窗口的中间点。Matlab 将其称为“对称”窗口，
  np.hanning() 返回该窗口。然而，对于傅里叶分析，它表示超过一个周期
  N-1 的余弦，因此不能在长度为 N 的傅里叶基中紧凑表示。相反，
  更好的做法是使用在最后零值之前结束的升余弦——即周期为 N 的
  完整余弦周期。Matlab 将其称为“周期性”窗口。本例程计算该窗口。

  Args:
    window_length: The number of points in the returned window.
    window_length: 返回窗口中的点数。

  Returns:
    A 1D np.array containing the periodic hann window.
    包含周期性 Hann 窗口的 1D np.array。
  """
  return 0.5 - (0.5 * np.cos(2 * np.pi / window_length *
                             np.arange(window_length)))


def stft_magnitude(signal, fft_length,
                   hop_length=None,
                   window_length=None):
  """Calculate the short-time Fourier transform magnitude.
      计算短时傅里叶变换的幅度。
  Args:
    signal: 1D np.array of the input time-domain signal.
    fft_length: Size of the FFT to apply.
    hop_length: Advance (in samples) between each frame passed to FFT.
    window_length: Length of each block of samples to pass to FFT.
    signal: 输入的时域信号，1D np.array。
    fft_length: 要应用的 FFT 大小。
    hop_length: 传递到 FFT 的每帧之间的推进步长（以样本数表示）。
    window_length: 传递到 FFT 的样本块的长度。

  Returns:
    2D np.array where each row contains the magnitudes of the fft_length/2+1
    unique values of the FFT for the corresponding frame of input samples.
    2D np.array，每行包含 fft_length/2+1 个唯一值的 FFT 对应帧的幅度。
  """
  frames = frame(signal, window_length, hop_length)
  # Apply frame window to each frame. We use a periodic Hann (cosine of period
  # window_length) instead of the symmetric Hann of np.hanning (period
  # window_length-1).
  """
  # 对每个帧应用窗函数。我们使用的是周期性 Hann (周期为 window_length)
  # 而不是 np.hanning 的对称 Hann (周期为 window_length-1)。
  """
  window = periodic_hann(window_length)
  windowed_frames = frames * window
  return np.abs(np.fft.rfft(windowed_frames, int(fft_length)))


# Mel spectrum constants and functions.Mel 频谱常数和函数。
_MEL_BREAK_FREQUENCY_HERTZ = 700.0
_MEL_HIGH_FREQUENCY_Q = 1127.0


def hertz_to_mel(frequencies_hertz):
  """Convert frequencies to mel scale using HTK formula.
      使用 HTK 公式将频率转换为 Mel 频率。
  Args:
    frequencies_hertz: Scalar or np.array of frequencies in hertz.
    frequencies_hertz: 以赫兹为单位的频率，标量或 np.array。
  Returns:
    Object of same size as frequencies_hertz containing corresponding values
    on the mel scale.
    与 frequencies_hertz 相同大小的对象，包含对应的 Mel 频率值。
  """
  return _MEL_HIGH_FREQUENCY_Q * np.log(
      1.0 + (frequencies_hertz / _MEL_BREAK_FREQUENCY_HERTZ))


def spectrogram_to_mel_matrix(num_mel_bins=20,
                              num_spectrogram_bins=129,
                              audio_sample_rate=8000,
                              lower_edge_hertz=125.0,
                              upper_edge_hertz=3800.0):
  """Return a matrix that can post-multiply spectrogram rows to make mel.
    返回一个矩阵，该矩阵用于将频谱图转换为mel频谱图。
  Returns a np.array matrix A that can be used to post-multiply a matrix S of
  spectrogram values (STFT magnitudes) arranged as frames x bins to generate a
  "mel spectrogram" M of frames x num_mel_bins.  M = S A.
  返回一个 np.array 矩阵 A，该矩阵可用于对频谱值 (STFT 幅值) 的矩阵 S
    进行后乘，该矩阵按帧 x bin 排列以生成帧 x num_mel_bins 的 "mel 频谱图" M。
    M = S A。

  The classic HTK algorithm exploits the complementarity of adjacent mel bands
  to multiply each FFT bin by only one mel weight, then add it, with positive
  and negative signs, to the two adjacent mel bands to which that bin
  contributes.  Here, by expressing this operation as a matrix multiply, we go
  from num_fft multiplies per frame (plus around 2*num_fft adds) to around
  num_fft^2 multiplies and adds.  However, because these are all presumably
  accomplished in a single call to np.dot(), it's not clear which approach is
  faster in Python.  The matrix multiplication has the attraction of being more
  general and flexible, and much easier to read.
  经典的 HTK 算法利用相邻 mel 频带的互补性，仅将每个 FFT bin 乘以一个 mel 权重，
    然后将其加到 bin 所贡献的两个相邻 mel 频带中，有正负符号。然而，通过将该操作
    表示为矩阵乘法，我们可以将每帧的 num_fft 次乘法（加上大约 2*num_fft 次加法）
    转换为大约 num_fft^2 次乘法和加法。然而，由于这些操作可能都通过单次调用 np.dot()
    完成，因此尚不清楚哪种方法在 Python 中更快。矩阵乘法的吸引力在于它更通用、更灵活，
    并且更容易阅读。
  Args:
    num_mel_bins: How many bands in the resulting mel spectrum.  This is
      the number of columns in the output matrix.
    num_spectrogram_bins: How many bins there are in the source spectrogram
      data, which is understood to be fft_size/2 + 1, i.e. the spectrogram
      only contains the nonredundant FFT bins.
    audio_sample_rate: Samples per second of the audio at the input to the
      spectrogram. We need this to figure out the actual frequencies for
      each spectrogram bin, which dictates how they are mapped into mel.
    lower_edge_hertz: Lower bound on the frequencies to be included in the mel
      spectrum.  This corresponds to the lower edge of the lowest triangular
      band.
    upper_edge_hertz: The desired top edge of the highest frequency band.
  num_mel_bins: 结果 mel 频谱中的频带数量。这是输出矩阵中的列数。
      num_spectrogram_bins: 源频谱数据中的 bin 数量，这理解为 fft_size/2 + 1，
        即频谱仅包含非冗余的 FFT bin。
      audio_sample_rate: 传入频谱的音频的采样率。我们需要这个来确定每个频谱 bin
        的实际频率，这决定了它们如何映射到 mel。
      lower_edge_hertz: 包含在 mel 频谱中的频率的下界。这对应于最低三角频带的下边缘。
      upper_edge_hertz: 最高频带的所需上边缘。

  Returns:
    An np.array with shape (num_spectrogram_bins, num_mel_bins).
    一个形状为 (num_spectrogram_bins, num_mel_bins) 的 np.array。

  Raises:
    ValueError: if frequency edges are incorrectly ordered or out of range.
    ValueError: 如果频率边缘顺序错误或超出范围。
  """
  nyquist_hertz = audio_sample_rate / 2.
  if lower_edge_hertz < 0.0:
    raise ValueError("lower_edge_hertz %.1f must be >= 0" % lower_edge_hertz)
  if lower_edge_hertz >= upper_edge_hertz:
    raise ValueError("lower_edge_hertz %.1f >= upper_edge_hertz %.1f" %
                     (lower_edge_hertz, upper_edge_hertz))
  if upper_edge_hertz > nyquist_hertz:
    raise ValueError("upper_edge_hertz %.1f is greater than Nyquist %.1f" %
                     (upper_edge_hertz, nyquist_hertz))
  spectrogram_bins_hertz = np.linspace(0.0, nyquist_hertz, num_spectrogram_bins)
  spectrogram_bins_mel = hertz_to_mel(spectrogram_bins_hertz)
  # The i'th mel band (starting from i=1) has center frequency
  # band_edges_mel[i], lower edge band_edges_mel[i-1], and higher edge
  # band_edges_mel[i+1].  Thus, we need num_mel_bins + 2 values in
  # the band_edges_mel arrays.
  band_edges_mel = np.linspace(hertz_to_mel(lower_edge_hertz),
                               hertz_to_mel(upper_edge_hertz), num_mel_bins + 2)
  # Matrix to post-multiply feature arrays whose rows are num_spectrogram_bins
  # of spectrogram values.
  mel_weights_matrix = np.empty((num_spectrogram_bins, num_mel_bins))
  for i in range(num_mel_bins):
    lower_edge_mel, center_mel, upper_edge_mel = band_edges_mel[i:i + 3]
    # Calculate lower and upper slopes for every spectrogram bin.
    # Line segments are linear in the *mel* domain, not hertz.
    lower_slope = ((spectrogram_bins_mel - lower_edge_mel) /
                   (center_mel - lower_edge_mel))
    upper_slope = ((upper_edge_mel - spectrogram_bins_mel) /
                   (upper_edge_mel - center_mel))
    # .. then intersect them with each other and zero.
    mel_weights_matrix[:, i] = np.maximum(0.0, np.minimum(lower_slope,
                                                          upper_slope))
  # HTK excludes the spectrogram DC bin; make sure it always gets a zero
  # coefficient.
  mel_weights_matrix[0, :] = 0.0
  return mel_weights_matrix


def log_mel_spectrogram(data,
                        audio_sample_rate=8000,
                        log_offset=0.0,
                        window_length_secs=0.025,
                        hop_length_secs=0.010,
                        **kwargs):
  """Convert waveform to a log magnitude mel-frequency spectrogram.
    将音频波形转换为对数 mel 频谱图
  Args:
    data: 1D np.array of waveform data.
    audio_sample_rate: The sampling rate of data.
    log_offset: Add this to values when taking log to avoid -Infs.
    window_length_secs: Duration of each window to analyze.
    hop_length_secs: Advance between successive analysis windows.
    **kwargs: Additional arguments to pass to spectrogram_to_mel_matrix.
    data: 1D np.array 形式的音频数据。
      audio_sample_rate: 音频的采样率。
      log_offset: 添加到 mel-spectrogram 的偏移量，以避免取对数时的负无穷值。
      window_length_secs: 传递到 FFT 的窗口大小（以秒为单位）。
      hop_length_secs: 传递到 FFT 的步长大小（以秒为单位）。
      **kwargs: 传递到 stft_magnitude() 和 spectrogram_to_mel_matrix() 的其他参数。

  Returns:
    2D np.array of (num_frames, num_mel_bins) consisting of log mel filterbank
    magnitudes for successive frames.
    形状为 (num_frames, num_mel_bins) 的 2D np.array，对应于对数 mel 频谱图。
  """
  window_length_samples = int(round(audio_sample_rate * window_length_secs))
  hop_length_samples = int(round(audio_sample_rate * hop_length_secs))
  fft_length = 2 ** int(np.ceil(np.log(window_length_samples) / np.log(2.0)))
  spectrogram = stft_magnitude(
      data,
      fft_length=fft_length,
      hop_length=hop_length_samples,
      window_length=window_length_samples)
  mel_spectrogram = np.dot(spectrogram, spectrogram_to_mel_matrix(
      num_spectrogram_bins=spectrogram.shape[1],
      audio_sample_rate=audio_sample_rate, **kwargs))
  return np.log(mel_spectrogram + log_offset)
