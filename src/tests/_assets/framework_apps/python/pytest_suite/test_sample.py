"""Sample pytest tests for testing debugging capabilities."""

import pytest


def test_simple_assertion():
    """Simple test for testing basic breakpoints."""
    x = 10  #:bp.test.x:
    y = 20  #:bp.test.y:
    result = x + y  #:bp.test.result:
    assert result == 30


def test_calculation():
    """Test for testing variable inspection and stepping."""
    a = 5  #:bp.calc.a:
    b = 3  #:bp.calc.b:
    product = a * b  #:bp.calc.product:
    total = a + b  #:bp.calc.total:
    assert product == 15
    assert total == 8


def test_variable_types():
    """Test with various variable types for inspection testing."""
    integer_var = 42  #:bp.vars.integer:
    string_var = "test"  #:bp.vars.string:
    list_var = [1, 2, 3, 4, 5]  #:bp.vars.list:
    dict_var = {"key1": "value1", "key2": "value2"}  #:bp.vars.dict:
    nested_dict = {  #:bp.vars.nested:
        "level1": {"level2": {"level3": "deep_value"}},
    }

    assert integer_var == 42
    assert string_var == "test"
    assert len(list_var) == 5
    assert dict_var["key1"] == "value1"
    assert nested_dict["level1"]["level2"]["level3"] == "deep_value"


@pytest.fixture
def sample_fixture():
    """Sample fixture for testing fixture debugging."""
    value = 100  #:bp.fixture.value:
    return value


def test_with_fixture(sample_fixture):
    """Test using a fixture."""
    result = sample_fixture * 2  #:bp.fixture.result:
    assert result == 200


class TestClass:
    """Test class for testing class-based test debugging."""

    def test_class_method(self):
        """Test method in a class."""
        x = 15  #:bp.class.x:
        y = 25  #:bp.class.y:
        total = x + y  #:bp.class.total:
        assert total == 40
