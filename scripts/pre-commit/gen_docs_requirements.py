from pathlib import Path

import tomli

# Define mappings from pyproject.toml sections to requirements.txt files
DOCS_MAPPINGS = {
    "docs": Path("docs/requirements.txt"),
}


def generate_requirements_file(
    pyproject_data: dict,
    section_name: str,
    output_path: Path,
    repo_root: Path,
) -> int:
    """Generate a requirements.txt file from a pyproject.toml section.

    Parameters
    ----------
    pyproject_data : dict
        Parsed pyproject.toml data
    section_name : str
        Section name in [project.optional-dependencies]
    output_path : Path
        Relative path to output requirements.txt file
    repo_root : Path
        Repository root directory

    Returns
    -------
    int
        Number of dependencies written
    """
    deps = (
        pyproject_data.get("project", {})
        .get("optional-dependencies", {})
        .get(section_name, [])
    )

    # Remove any trailing commas or whitespace, sort, and deduplicate
    deps = sorted(set(dep.strip().rstrip(",") for dep in deps))

    # Create full output path
    full_output_path = repo_root / output_path
    full_output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write requirements file
    header = f"# Auto-generated from pyproject.toml [project.optional-dependencies.{section_name}]\n"
    with full_output_path.open("w") as f:
        f.write(header)
        for dep in deps:
            f.write(f"{dep}\n")

    return len(deps)


def main():
    """Generate all docs requirements files from pyproject.toml."""
    repo_root = Path(__file__).parent.parent.parent
    pyproject_path = repo_root / "pyproject.toml"

    with pyproject_path.open("rb") as f:
        pyproject = tomli.load(f)

    total_files = 0
    total_deps = 0

    for section_name, output_path in DOCS_MAPPINGS.items():
        try:
            dep_count = generate_requirements_file(
                pyproject,
                section_name,
                output_path,
                repo_root,
            )
            print(
                f"Wrote {dep_count} dependencies to {output_path} (from {section_name})",
            )
            total_files += 1
            total_deps += dep_count
        except KeyError:
            print(f"Warning: Section '{section_name}' not found in pyproject.toml")

    print(
        f"Generated {total_files} requirements files with {total_deps} total dependencies",
    )


if __name__ == "__main__":
    main()
