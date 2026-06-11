"""Sample module fixture for chunking tests."""


MODULE_CONSTANT_ONE = 1
MODULE_CONSTANT_TWO = 2
MODULE_CONSTANT_THREE = 3
MODULE_CONSTANT_FOUR = 4
MODULE_CONSTANT_FIVE = 5
MODULE_CONSTANT_SIX = 6


@sample_decorator
def decorated_function(argument_value):
    """Decorated function docstring."""
    return argument_value


class SampleService:
    """Service docstring."""

    def first_method(self):
        """First method docstring."""
        return MODULE_CONSTANT_ONE

    def second_method(self):
        return MODULE_CONSTANT_TWO


async def async_function():
    """Async docstring."""
    return MODULE_CONSTANT_THREE
