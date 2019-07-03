Integrate cmd2 into your project
--------------------------------

[TODO - show how to use semantic versions to add the correct version string to setup.py ]

[TODO - this is probably outdated advice]

``cmd2`` is contained in a small number of Python files, which can be easily
copied into your project.  *The copyright and license notice must be retained*.

This is an option suitable for advanced Python users.  You can simply include
the files within your project's hierarchy. If you want to modify ``cmd2``, this
may be a reasonable option.  Though, we encourage you to use stock ``cmd2`` and
either composition or inheritance to achieve the same goal.

This approach will obviously NOT automatically install the required 3rd-party
dependencies, so you need to make sure the following Python packages are
installed:

  * attrs
  * colorama
  * pyperclip
  * wcwidth

On Windows, there is an additional dependency:

  * pyreadline