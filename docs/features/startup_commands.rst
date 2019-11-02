Startup Commands
================

``cmd2`` provides a couple different ways for running commands immediately
after your application starts up:

1. :ref:`features/misc:Commands At Invocation`
1. :ref:`features/misc:Initialization Script`

Commands run as part of a startup (initialization) script are always run
immediately after the application finishes initializing so they are
guaranteed to run before any *Commands At Invocation*.

