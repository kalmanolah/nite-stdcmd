"""This file contains the NITE Standard Command module."""
import logging
import os
import socket
import asyncore
import threading
from prettytable import PrettyTable
from nite.module import AbstractModule
from nite.event import EventPriority, BaseEvent


logger = logging.getLogger(__name__)


class CommandEvent(BaseEvent):

    """Event wrapper around an executed command."""

    @property
    def command(self):
        """Return command."""
        return self._command

    @command.setter
    def command(self, value):
        """Set command."""
        self._command = value

    @property
    def response(self):
        """Return response."""
        return self._response

    @response.setter
    def response(self, value):
        """Set response."""
        self._response = value

    @property
    def handled(self):
        """Return a boolean indicating whether or not this command has been handled."""
        return self._handled

    @handled.setter
    def handled(self, value):
        """Set a boolean indicating whether or not this command has been handled."""
        self._handled = value

    def __init__(self, command):
        """Create and populate the event."""
        super(BaseEvent, self).__init__()
        self.command = command
        self.handled = False
        self.response = None


class CommandHandler(asyncore.dispatcher_with_send):

    """This class contains a handler for commands."""

    @property
    def client_address(self):
        """Return client address."""
        return self._client_address

    @client_address.setter
    def client_address(self, value):
        """Set client address."""
        self._client_address = value

    @property
    def server(self):
        """Return server."""
        return self._server

    @server.setter
    def server(self, value):
        """Set server."""
        self._server = value

    def __init__(self, socket, server, client_address='Unknown'):
        """Constructor."""
        super(self.__class__, self).__init__(socket)
        self.client_address = client_address
        self.server = server

    def handle_read(self):
        """Read data from the socket."""
        data = self.recv(8192).rstrip().decode('UTF8', 'ignore')

        if data:
            cmd_event = CommandEvent(data)
            self.server.module.NITE.events.handle(cmd_event)

            if cmd_event.response:
                self.send((cmd_event.response + "\n").encode('UTF8'))

    def handle_close(self):
        """Handle a disconnection."""
        self.close()
        logger.debug('Client "%s" disconnected from command server', self.client_address)


class CommandServer(asyncore.dispatcher):

    """This class contains the command server."""

    @property
    def module(self):
        """Return module."""
        return self._module

    @module.setter
    def module(self, value):
        """Set module."""
        self._module = value

    def __init__(self, bind_address, listen_backlog, module):
        """Constructor."""
        super(self.__class__, self).__init__()
        self.module = module

        # Try to autodetect socket type
        split = bind_address.split(':')
        socket_type = socket.AF_UNIX if len(split) == 1 else socket.AF_INET

        self.create_socket(socket_type, socket.SOCK_STREAM)
        self.set_reuse_addr()

        if socket_type is socket.AF_UNIX:
            try:
                os.remove(bind_address)
                logger.debug('Removed stale socket file "%s"', bind_address)
            except OSError:
                pass

            bind_args = bind_address
        else:
            bind_args = (':'.join(split[0:-1]), int(split[-1]))

        logger.debug('Binding socket to "%s"', bind_address)
        self.bind(bind_args)

        logger.debug('Setting socket listen backlog to "%s"', listen_backlog)
        self.listen(listen_backlog)

    def handle_accept(self):
        """Handle acception of a new connection."""
        sock, addr = self.accept()

        addr = ':'.join(list([str(x) for x in addr])) if addr else 'Unknown'
        logger.debug('Client "%s" connected to command server', addr)

        CommandHandler(socket=sock, server=self, client_address=addr)


class StdCmd(AbstractModule):

    """This class contains the NITE Standard Command module."""

    @property
    def handlers(self):
        """Return command handlers."""
        return self._handlers

    @handlers.setter
    def handlers(self, value):
        """Set command handlers."""
        self._handlers = value

    @property
    def server(self):
        """Return command server."""
        return self._server

    @server.setter
    def server(self, value):
        """Set command server."""
        self._server = value

    @property
    def thread(self):
        """Return server thread."""
        return self._thread

    @thread.setter
    def thread(self, value):
        """Set server thread."""
        self._thread = value

    @property
    def terminate(self):
        """Return termination event."""
        return self._terminate

    @terminate.setter
    def terminate(self, value):
        """Set termination event."""
        self._terminate = value

    def start(self):
        """Start the module."""
        # Set command handlers
        self.handlers = {
            'help': ["Show this help menu", self.on_help_command],
            'stop': ["Stop NITE", self.on_stop_command],
            'reload': ["Reload NITE", self.on_reload_command]
        }

        bind_address = self.NITE.config.get('nite.command.bind_address', '/tmp/nite.sock')
        listen_backlog = int(self.NITE.config.get('nite.command.listen_backlog', '5'))

        if bind_address:
            logger.debug('Creating a thread to run the command server')
            kwargs = {'bind_address': bind_address, 'listen_backlog': listen_backlog}

            self.thread = threading.Thread(target=self.create_server, kwargs=kwargs)
            self.terminate = threading.Event()
            self.thread.start()

        # Register an executor for commands
        self.NITE.events.register(CommandEvent, self.on_command, EventPriority.LOWEST)

    def stop(self):
        """Stop the module."""
        if self.thread:
            logger.debug('Attempting to terminate the command server thread')
            self.terminate.set()
            # self.thread.join() # Joining is not okay, because this command is called from the command server thread

    def create_server(self, bind_address, listen_backlog):
        """Create the command server."""
        self.server = CommandServer(bind_address=bind_address, listen_backlog=listen_backlog, module=self)

        while not self.terminate.is_set():
            asyncore.loop(timeout=5, count=1)

        self.server.close()

    def on_command(self, cmd_event):
        """Handle a command event."""
        # If the command has already been handled, there is nothing left to do.
        if cmd_event.handled:
            return

        command = cmd_event.command.split(' ')[0]

        if command in self.handlers:
            self.handlers[command][1](cmd_event)
        else:
            cmd_event.response = 'Invalid command: %s\nTry using "help" for a list of commands' % cmd_event.command

    def on_stop_command(self, cmd_event):
        """Handle a stop command."""
        self.NITE.stop()

    def on_reload_command(self, cmd_event):
        """Handle a reload command."""
        self.NITE.stop()
        self.NITE.start()

    def on_help_command(self, cmd_event):
        """Handle a help command."""
        table = PrettyTable(['Command', 'Description'])
        table.align = 'l'
        table.max_width = int(os.popen('stty size', 'r').read().split()[0])

        [table.add_row([cmd, meta[0]]) for cmd, meta in self.handlers.items()]
        cmd_event.response = str(table)
