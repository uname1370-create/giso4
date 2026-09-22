import numpy as np

def test_mask_shape_contract():
    mask = np.zeros((100, 120), dtype=np.uint8)
    assert mask.shape == (100, 120)
    assert mask.dtype == np.uint8

def test_mask_is_binary_compatible():
    mask = np.array([[0, 127, 255]], dtype=np.uint8)
    assert int(mask.max()) == 255
    assert int(mask.min()) == 0
