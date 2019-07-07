Documentation Conventions
=========================

Guiding Principles
------------------

Follow the `Documentation Principles
<http://www.writethedocs.org/guide/writing/docs-principles/>`_ described by
`Write The Docs <http://www.writethedocs.org>`_

In addition:

- We have gone to great lengths to retain compatibility with the standard
  library cmd, the documentation should make it easy for developers to
  understand how to move from cmd to cmd2, and what benefits that will provide
- We should provide both descriptive and reference documentation.
- API reference documentation should be generated from docstrings in the code
- Documentation should include rich hyperlinking to other areas of the
  documentation, and to the API reference


Naming Files
------------

- all lower case file names
- if the name has multiple words, separate them with an underscore
- all documentation file names end in '.rst'


Heirarchy of headings
---------------------

show the heirarchy of sphinx headings we use, and the conventions (underline
only, no overline)

Use '=', then '-', then '~'. If your document needs more levels than that,
break it into separate documents.

You only have to worry about the heirarchy of headings within a single file.
Sphinx handles the intra-file heirarchy magically on it's own.

Use two blank lines before every heading unless it's the first heading in the
file. Use one blank line after every heading


Code
----

This documentation declares python as the default Sphinx domain.  Python code
or interactive python sessions can be presented by either:

- finishing the preceding paragraph with a ``::`` and indenting the code
- use the ``.. code-block::`` directive

If you want to show other code, like shell commands, then use ``.. code-block:
shell``.


Table of Contents and Captions
------------------------------


Hyperlinks
----------

If you want to use an external hyperlink target, define the target at the top
of the page, not the bottom.


We use the Sphinx `autosectionlabel
<http://www.sphinx-doc.org/en/master/usage/extensions/autosectionlabel.html>`_
extension. This allows you to reference any header in any document by::

   See :ref:`features/argument_processing:Help Messages`

or ::

   See :ref:`custom title<features/argument_processing:Help Messages>`

Which render like

See :ref:`features/argument_processing:Help Messages`

and

See :ref:`custom title<features/argument_processing:Help Messages>`

[TODO what's the right way to link to source code? Can we make it link to the
tag that the documentation is rendered from?]


Autolinking
-----------


Referencing cmd2 API documentation
----------------------------------


Info and Warning Callouts
-------------------------


Wrapping
--------

Hard wrap all text with line lengths no greater than 79 characters. It makes
everything easier when editing documentation, and has no impact on reading
documentation because we render to html.


Referencing cmd2
-----------------

Whenever you reference ``cmd2`` in the documentation, enclose it in double
backticks. This indicates an inline literal in restructured text, and makes it
stand out when rendered as html.

Style Checker
-------------

Use `doc8 <https://pypi.org/project/doc8/>`_ to check the style of the
documentation. This tool can be invoked using the proper options by typing:

.. code-block:: shell

   $ invoke doc8

