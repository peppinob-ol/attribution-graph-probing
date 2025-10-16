import pytest
import torch


@pytest.fixture(autouse=True)
def set_torch_seed() -> None:
    torch.manual_seed(42)
