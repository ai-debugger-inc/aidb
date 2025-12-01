"""Views for testing Django debugging capabilities."""

from django.http import HttpResponse, JsonResponse


def home_view(request):
    """Simple home view for testing basic breakpoints."""
    message = "Hello from Django"  #:bp.home.message:
    counter = 42  #:bp.home.counter:
    result = f"{message} - Counter: {counter}"  #:bp.home.result:
    return HttpResponse(result)


def calculate_view(request, a, b):
    """View for testing variable inspection and stepping."""
    x = a * 2  #:bp.calc.x:
    y = b * 3  #:bp.calc.y:
    total = x + y  #:bp.calc.total:
    result = {  #:bp.calc.result:
        "a": a,
        "b": b,
        "x": x,
        "y": y,
        "total": total,
    }
    return JsonResponse(result)


def variable_inspection_view(request):
    """View with various variable types for inspection testing."""
    integer_var = 42  #:bp.vars.integer:
    string_var = "test"  #:bp.vars.string:
    list_var = [1, 2, 3, 4, 5]  #:bp.vars.list:
    dict_var = {"key1": "value1", "key2": "value2"}  #:bp.vars.dict:
    nested_dict = {  #:bp.vars.nested:
        "level1": {"level2": {"level3": "deep_value"}},
    }

    response_data = {
        "integer": integer_var,
        "string": string_var,
        "list": list_var,
        "dict": dict_var,
        "nested": nested_dict,
    }
    return JsonResponse(response_data)
