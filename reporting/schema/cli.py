import json

import click

from reporting.schema import reporting_config


@click.group()
def schema_cli() -> None:
    """Reporting schema tools."""


@schema_cli.command("export")
@click.option("--output-file")
def export_json_schema(output_file: str | None) -> None:
    """
    Export the reporting schema and print it to stdout. If
    --output-file is provided, the schema will be written to
    that file.
    """
    schema_dict = reporting_config.output_json_schema()
    schema_as_json = json.dumps(schema_dict, indent=4)
    if output_file:
        with open(output_file, "w") as f:
            f.write(schema_as_json)
    else:
        print(schema_as_json)


if __name__ == "__main__":
    schema_cli()
