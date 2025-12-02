"""YAML parser for converting scenario definitions to AST."""

from pathlib import Path
from typing import Any

from aidb_cli.generators.core.types import (
    ArrayConstruct,
    ComplexityLevel,
    ConditionalConstruct,
    Construct,
    DataType,
    ExceptionConstruct,
    FunctionConstruct,
    LoopConstruct,
    LoopType,
    Parameter,
    PrintConstruct,
    ReturnConstruct,
    Scenario,
    ScenarioCategory,
    SyntaxErrorConstruct,
    ValidationRule,
    VariableConstruct,
)
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class ScenarioParser:
    """Parse YAML scenario definitions into AST."""

    def __init__(self) -> None:
        """Initialize parser with construct type mapping."""
        self._construct_parsers = {
            "variable": self.parse_variable,
            "loop": self.parse_loop,
            "function": self.parse_function,
            "conditional": self.parse_conditional,
            "exception": self.parse_exception,
            "print": self.parse_print,
            "return": self.parse_return,
            "syntax_error": self.parse_syntax_error,
            "array": self.parse_array,
        }

    def parse_file(self, file_path: Path) -> list[Scenario]:
        """Parse scenarios from a YAML file.

        Args
        ----
            file_path: Path to YAML file

        Returns
        -------
            List of parsed scenarios
        """
        from aidb_cli.core.yaml import safe_read_yaml

        data = safe_read_yaml(file_path)

        if "scenarios" not in data:
            msg = f"No scenarios found in {file_path}"
            raise ValueError(msg)

        scenarios = []
        for scenario_data in data["scenarios"]:
            scenario = self.parse_scenario(scenario_data)
            scenarios.append(scenario)

        return scenarios

    def parse_scenario(self, data: dict[str, Any]) -> Scenario:
        """Parse a single scenario from YAML data.

        Args
        ----
            data: Scenario YAML data

        Returns
        -------
            Parsed Scenario object
        """
        # Required fields
        scenario_id = data.get("id")
        if not scenario_id:
            msg = "Scenario missing required 'id' field"
            raise ValueError(msg)

        name = data.get("name", scenario_id)
        description = data.get("description", "")

        # Parse category and complexity
        category_str = data.get("category", "debugging")
        try:
            category = ScenarioCategory(category_str)
        except ValueError:
            category = ScenarioCategory.DEBUGGING

        complexity_str = data.get("complexity", "basic")
        try:
            complexity = ComplexityLevel(complexity_str)
        except ValueError:
            complexity = ComplexityLevel.BASIC

        # Parse constructs
        constructs_data = data.get("constructs", [])
        constructs = self.parse_constructs(constructs_data)

        # Parse expected markers
        expected_markers = data.get("expected_markers", {})

        # Parse validation rules
        validation_data = data.get("validation", [])
        validation_rules = []
        for rule_data in validation_data:
            if isinstance(rule_data, dict):
                rule = ValidationRule(
                    type=rule_data.get("type", "unknown"),
                    criteria=rule_data.get("criteria", ""),
                    description=rule_data.get("description"),
                )
                validation_rules.append(rule)

        return Scenario(
            id=scenario_id,
            name=name,
            description=description,
            category=category,
            complexity=complexity,
            constructs=constructs,
            expected_markers=expected_markers,
            validation=validation_rules,
        )

    def parse_constructs(
        self,
        constructs_data: list[dict[str, Any]],
    ) -> list[Construct]:
        """Parse a list of constructs.

        Args
        ----
            constructs_data: List of construct YAML data

        Returns
        -------
            List of parsed Construct objects
        """
        constructs = []
        for construct_data in constructs_data:
            construct = self.parse_construct(construct_data)
            if construct:
                constructs.append(construct)
        return constructs

    def parse_construct(self, data: dict[str, Any]) -> Construct | None:
        """Parse a single construct from YAML data.

        Args
        ----
            data: Construct YAML data

        Returns
        -------
            Parsed Construct object or None
        """
        construct_type = data.get("type")
        if not construct_type:
            return None

        marker = data.get("marker")

        try:
            parser_func = self._construct_parsers.get(construct_type)
            if parser_func:
                return parser_func(data, marker)

            logger.warning("Unknown construct type: %s", construct_type)
            return None
        except Exception as e:  # Return None for unparseable constructs
            logger.error("Error parsing construct: %s", e)
            return None

    def parse_variable(
        self,
        data: dict[str, Any],
        marker: str | None,
    ) -> VariableConstruct:
        """Parse a variable construct."""
        name = data.get("name", "unnamed_var")
        data_type_str = data.get("data_type")
        data_type = self.parse_data_type(data_type_str) if data_type_str else None

        return VariableConstruct(
            name=name,
            data_type=data_type,
            initial_value=data.get("initial_value"),
            operation=data.get("operation"),
            value=data.get("value"),
            scope=data.get("scope", "local"),
            marker=marker,
        )

    def parse_loop(self, data: dict[str, Any], marker: str | None) -> LoopConstruct:
        """Parse a loop construct."""
        loop_type_str = data.get("loop_type", "for")
        try:
            loop_type = LoopType(loop_type_str)
        except ValueError:
            loop_type = LoopType.FOR

        # Parse loop body
        body_data = data.get("body", [])
        body = self.parse_constructs(body_data)

        return LoopConstruct(
            loop_type=loop_type,
            variable=data.get("variable"),
            start=data.get("start"),
            end=data.get("end"),
            step=data.get("step", 1),
            condition=data.get("condition"),
            iterable=data.get("iterable"),
            body=body,
            marker=marker,
        )

    def parse_function(
        self,
        data: dict[str, Any],
        marker: str | None,
    ) -> FunctionConstruct:
        """Parse a function construct."""
        name = data.get("name", "unnamed_func")

        # Parse parameters
        params_data = data.get("parameters", [])
        parameters = []
        for param_data in params_data:
            if isinstance(param_data, dict):
                param = Parameter(
                    name=param_data.get("name", "param"),
                    data_type=self.parse_data_type(param_data.get("type")),
                )
                parameters.append(param)

        # Parse return type
        return_type_str = data.get("return_type")
        return_type = self.parse_data_type(return_type_str) if return_type_str else None

        # Parse function body
        body_data = data.get("body", [])
        body = self.parse_constructs(body_data)

        # For function calls
        operation = data.get("operation")
        arguments = data.get("arguments", [])
        result_variable = data.get("result_variable")

        return FunctionConstruct(
            name=name,
            parameters=parameters,
            return_type=return_type,
            body=body,
            operation=operation,
            arguments=arguments,
            result_variable=result_variable,
            marker=marker,
        )

    def parse_conditional(
        self,
        data: dict[str, Any],
        marker: str | None,
    ) -> ConditionalConstruct:
        """Parse a conditional construct."""
        condition = data.get("condition", "true")

        # Parse true/false bodies
        true_body_data = data.get("true_body", data.get("body", []))
        true_body = self.parse_constructs(true_body_data)

        false_body_data = data.get("false_body", [])
        false_body = self.parse_constructs(false_body_data)

        return ConditionalConstruct(
            condition=condition,
            true_body=true_body,
            false_body=false_body,
            marker=marker,
        )

    def parse_exception(
        self,
        data: dict[str, Any],
        marker: str | None,
    ) -> ExceptionConstruct:
        """Parse an exception construct."""
        exception_type = data.get("exception_type", "try")

        # Parse try body
        body_data = data.get("body", [])
        body = self.parse_constructs(body_data)

        # Parse catch blocks and their bodies
        catch_blocks_data = data.get("catch_blocks", [])
        parsed_catch_blocks = []
        for catch_block in catch_blocks_data:
            parsed_catch = {
                "exception_class": catch_block.get("exception_class", "Exception"),
                "marker": catch_block.get("marker", ""),
                "body": self.parse_constructs(catch_block.get("body", [])),
            }
            parsed_catch_blocks.append(parsed_catch)

        # Parse finally block and its body
        finally_block_data = data.get("finally_block")
        parsed_finally_block = None
        if finally_block_data:
            parsed_finally_block = {
                "marker": finally_block_data.get("marker", ""),
                "body": self.parse_constructs(finally_block_data.get("body", [])),
            }

        return ExceptionConstruct(
            exception_type=exception_type,
            body=body,
            catch_blocks=parsed_catch_blocks,
            finally_block=parsed_finally_block,
            marker=marker,
        )

    def parse_print(self, data: dict[str, Any], marker: str | None) -> PrintConstruct:
        """Parse a print construct."""
        message = data.get("message", data.get("value", ""))
        values = data.get("values", [])

        # Extract variables from message template
        if "{" in message:
            import re

            pattern = r"\{(\w+)\}"
            found_vars = re.findall(pattern, message)
            if found_vars and not values:
                values = found_vars

        return PrintConstruct(
            message=message,
            values=values,
            marker=marker,
        )

    def parse_return(self, data: dict[str, Any], marker: str | None) -> ReturnConstruct:
        """Parse a return construct."""
        return ReturnConstruct(
            value=data.get("value"),
            marker=marker,
        )

    def parse_syntax_error(
        self,
        data: dict[str, Any],
        marker: str | None,
    ) -> SyntaxErrorConstruct:
        """Parse a syntax error construct."""
        return SyntaxErrorConstruct(
            error_type=data.get("error_type", "generic"),
            code_snippet=data.get("code_snippet", "# SYNTAX ERROR"),
            marker=marker,
        )

    def parse_array(self, data: dict[str, Any], marker: str | None) -> ArrayConstruct:
        """Parse an array construct."""
        name = data.get("name", "unnamed_array")
        data_type = self.parse_data_type(data.get("data_type", "integer"))

        return ArrayConstruct(
            name=name,
            data_type=data_type,
            size=data.get("size"),
            values=data.get("values", []),
            initialize=data.get("initialize"),
            marker=marker,
        )

    def parse_data_type(self, type_str: str | None) -> DataType | None:
        """Parse a data type string."""
        if not type_str:
            return None

        type_map = {
            "integer": DataType.INTEGER,
            "int": DataType.INTEGER,
            "float": DataType.FLOAT,
            "double": DataType.FLOAT,
            "string": DataType.STRING,
            "str": DataType.STRING,
            "boolean": DataType.BOOLEAN,
            "bool": DataType.BOOLEAN,
            "array": DataType.ARRAY,
            "list": DataType.ARRAY,
            "map": DataType.MAP,
            "dict": DataType.MAP,
            "object": DataType.OBJECT,
        }

        return type_map.get(type_str.lower())
