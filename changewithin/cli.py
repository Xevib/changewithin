# -*- coding: utf-8 -*-
import click
from raven import Client
from changewithin import ChangeWithin


@click.group()
def changeswithin():
    pass


@changeswithin.command()
@click.option('--host', default=None)
@click.option('--db', default=None)
@click.option('--user', default=None)
@click.option('--password', default=None)
@click.option('--initialize/--no-initialize', default=False)
def changeswithin(host, db, user, password, initialize):
    """

    :param host:
    :param db:
    :param user:
    :param password:
    :return:
    """

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