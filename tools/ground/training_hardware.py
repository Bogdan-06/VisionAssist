"""Explicit TensorFlow device selection shared by training and its hardware check."""
def configure(device, threads):
    import tensorflow as tf
    if device not in ('auto', 'cpu', 'gpu') or threads < 1:
        raise ValueError('Invalid training device or thread count')
    tf.config.threading.set_intra_op_parallelism_threads(threads)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    available = tf.config.list_physical_devices('GPU')
    if device == 'cpu':
        tf.config.set_visible_devices([], 'GPU')
    elif device == 'gpu' and not available:
        raise RuntimeError('GPU requested but TensorFlow cannot see it. Use the configured WSL2 environment.')
    else:
        # Allocate on demand so the 4 GiB laptop GPU is not reserved in full.
        for gpu in available:
            tf.config.experimental.set_memory_growth(gpu, True)
    active = [] if device == 'cpu' else available
    return dict(requested=device, selected='gpu' if active else 'cpu', cpu_threads=threads,
                gpus=[dict(name=gpu.name, **tf.config.experimental.get_device_details(gpu)) for gpu in active])
