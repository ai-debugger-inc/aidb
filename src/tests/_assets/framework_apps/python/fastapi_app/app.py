"""FastAPI test application for debugging capabilities testing."""

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI()

# Dynamic port from environment, with fallback for manual testing
DEFAULT_PORT = 8000
APP_PORT = int(os.environ.get("APP_PORT", DEFAULT_PORT))


@app.get("/")
async def home_view():
    """Simple home view for testing basic breakpoints."""
    message = "Hello from FastAPI"  #:bp.home.message:
    counter = 42  #:bp.home.counter:
    result = f"{message} - Counter: {counter}"  #:bp.home.result:
    return {"message": result}


@app.get("/calculate/{a}/{b}")
async def calculate_view(a: int, b: int):
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
    return result


@app.get("/variables")
async def variable_inspection_view():
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
    return response_data


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=APP_PORT, log_level="info")
