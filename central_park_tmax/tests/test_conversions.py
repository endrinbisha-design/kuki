import numpy as np

from central_park_tmax.constants import c_to_f, f_to_c


def test_known_conversions():
    assert abs(c_to_f(0) - 32.0) < 1e-9
    assert abs(c_to_f(100) - 212.0) < 1e-9
    assert abs(c_to_f(37) - 98.6) < 1e-9
    assert abs(f_to_c(32) - 0.0) < 1e-9
    assert abs(f_to_c(212) - 100.0) < 1e-9


def test_roundtrip():
    for f in np.linspace(-20, 110, 40):
        assert abs(c_to_f(f_to_c(f)) - f) < 1e-9


def test_ghcn_tenths_scaling():
    # GHCN stores tenths of degC; 356 -> 35.6 C -> 96.08 F
    celsius = 356 / 10.0
    assert abs(c_to_f(celsius) - 96.08) < 1e-6
