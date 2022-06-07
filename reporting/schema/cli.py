import json
from typing import Optional

import click
from flask import Flask
from flask.cli import AppGroup

from reporting.schema import reporting_config

app = Flask(__name__)
schema_cli = AppGroup("schema")
app.cli.add_command(schema_cli)


@schema_cli.command("export")
@click.option("--output-file")
def export_json_schema(output_file: Optional[str]) -> None:
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
