# -*- coding: utf-8 -*-
import click
from raven import Client
from changewithin import ChangeWithin


@click.group()
def changeswithin():
    pass


@changeswithin.command()
def changeswithin(**kwargs):
    client = Client()
    try:
        c = ChangeWithin()
        c.load_config()
        c.process_file()
        c.report()
    except Exception:
        client.captureException()

        
def cli_generate_report():
    changeswithin()