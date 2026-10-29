"""Require a real TensorFlow GPU convolution, not just an installed driver."""
import json
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import tensorflow as tf
from training_hardware import configure

if __name__ == '__main__':
    hardware = configure('gpu', 8)
    with tf.device('/GPU:0'):
        output = tf.nn.conv2d(tf.ones((1, 32, 32, 3)), tf.ones((3, 3, 3, 8)), strides=1, padding='VALID')
        checksum = float(tf.reduce_sum(output).numpy())
    if 'GPU:' not in output.device or checksum != 194400.0:
        raise RuntimeError('GPU convolution failed its placement/value check')
    print(json.dumps(dict(hardware=hardware, tensorflow=tf.__version__, output_device=output.device,
                          convolution_checksum=checksum, verified=True), indent=2))
