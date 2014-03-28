# -*- coding: utf-8 -*-
"""
pen.cli - command line stuff
"""

from clint import arguments
from clint.textui import colored, puts

from . import __version__
from .core import ExitStatus, show_error
from .core import cmd_path, cmd_all, cmd_list, cmd_delete, cmd_create_list, cmd_touch_note
from .storage import store

args = arguments.Args()

def main():
    arg = args.get(0)
    store.read()
    if arg:
        command = Command.lookup(arg)
        if command:
            execute(command)
        elif args.contains(('-h', '--help')):
            display_info()
        elif args.contains(('-v', '--version')):
            puts('{0} v{1}'.format(
                colored.yellow('pen'),
                __version__
            ))
        else:
            cmd_touch_note(args)
    else:
        cmd_list(args)
    store.save()
    return ExitStatus.OK


def execute(command):
    arg = args.get(0)
    args.remove(arg)
    command.__call__(args)


def display_info():
    puts('{0}. {1}'.format(
        colored.yellow('pen'), 'A Cecil Woebker Project.'))

    puts('Usage: {0} {1}'.format(
        colored.yellow('pen'), colored.green('<command> | <note>')))
    puts('-----------------------------')
    for command in Command.all_commands():
        usage = command.usage or command.name
        help = command.help or ''
        puts('{0:40} {1}'.format(
                colored.green(usage),
                help))


def cmd_help(args):
    command = args.get(0)
    if command == None:
        display_info()
        return
    elif not Command.lookup(command):
        command = 'help'
        show_error(colored.red('Unknown command: {0}'.format(args.get(0))))
    cmd = Command.lookup(command)
    usage = cmd.usage or ''
    help = cmd.help or ''
    help_text = '%s - %s' % (usage, help)
    puts(help_text)


### Commands
class Command(object):
    COMMANDS = {}
    SHORT_MAP = {}

    @classmethod
    def register(klass, command):
        klass.COMMANDS[command.name] = command
        if command.short:
            for short in command.short:
                klass.SHORT_MAP[short] = command

    @classmethod
    def lookup(klass, name):
        if name in klass.SHORT_MAP:
            return klass.SHORT_MAP[name]
        if name in klass.COMMANDS:
            return klass.COMMANDS[name]
        else:
            return None

    @classmethod
    def all_commands(klass):
        return sorted(list(klass.COMMANDS.values()),
                      key=lambda cmd: cmd.name)

    def __init__(self, name=None, short=None, fn=None, usage=None, help=None):
        self.name = name
        self.short = short
        self.fn = fn
        self.usage = usage
        self.help = help

    def __call__(self, *args, **kw_args):
        return self.fn(*args, **kw_args)


def define_command(name=None, short=None, fn=None, usage=None, help=None):
    command = Command(name=name, short=short, fn=fn, usage=usage, help=help)
    Command.register(command)


define_command(name='help', short=['h'], fn=cmd_help, usage='help <command>',
    help='Display help for a command.')

define_command(name='path', fn=cmd_path, usage='path (<pen_file_path>)',
    help='Sets Pen Storage Path')

#define_command(name='list', fn=cmd_list, usage='list (<note>)',
#    help='List elements.')

define_command(name='all', fn=cmd_all, usage='all',
    help='List everything recursively.')

define_command(name='create', fn=cmd_create_list, usage='create <list>',
    help='Create a list.')

define_command(name='delete', fn=cmd_delete, usage='delete',
    help='Delete a list or note.')
