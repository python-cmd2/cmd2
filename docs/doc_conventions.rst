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


Style Checker
-------------

Use `doc8 <https://pypi.org/project/doc8/>`_ to check the style of the
documentation. This tool can be invoked using the proper options by typing:

.. code-block:: shell

   $ invoke doc8


Naming Files
------------

All source files in the documentation must:

- have all lower case file names
- if the name has multiple words, separate them with an underscore
- end in '.rst'


Indenting
---------

In reStructuredText all indenting is significant. Use 2 spaces per indenting
level.


Wrapping
--------

Hard wrap all text so that line lengths are no greater than 79 characters. It
makes everything easier when editing documentation, and has no impact on
reading documentation because we render to html.


Titles and Headings
-------------------

reStructuredText allows flexibility in how headings are defined. You only have
to worry about the heirarchy of headings within a single file. Sphinx magically
handles the intra-file heirarchy on it's own. This magic means that no matter
how you style titles and headings in the various files that comprise the
documentation, Sphinx will render properly structured output. To ensure we have
a similar consistency when viewing the source files, we use the following
conventions for titles and headings:

1. When creating a heading for a section, do not use the overline and underline
syntax. Use the underline syntax only::

  Document Title
  ==============

2. The string of adornment characters on the line following the heading should
be the same length as the title.

3. The title of a document should use the '=' adornment character on the next
line and only one heading of this level should appear in each file.

4. Sections within a document should have their titles adorned with the '-'
character::

  Section Title
  -------------

5. Subsections within a section should have their titles adorned with the '~'
character::

  Subsection Title
  ~~~~~~~~~~~~~~~~

6. Use two blank lines before every title unless it's the first heading in the
file. Use one blank line after every heading.

7. If your document needs more than three levels of sections, break it into
separate documents.


Inline Code
-----------

This documentation declares ``python`` as the default Sphinx domain.  Python
code or interactive Python sessions can be presented by either:

- finishing the preceding paragraph with a ``::`` and indenting the code
- use the ``.. code-block::`` directive

If you want to show non-Python code, like shell commands, then use ``..
code-block: shell``.


External Hyperlinks
-------------------

If you want to use an external hyperlink target, define the target at the top
of the page or the top of the section, not the bottom. The target definition
should always appear before it is referenced.


Links To Other Documentation Pages and Sections
-----------------------------------------------

We use the Sphinx `autosectionlabel
<http://www.sphinx-doc.org/en/master/usage/extensions/autosectionlabel.html>`_
extension. This allows you to reference any header in any document by::

   See :ref:`features/argument_processing:Help Messages`

or::

   See :ref:`custom title<features/argument_processing:Help Messages>`

Which render like

See :ref:`features/argument_processing:Help Messages`

and

See :ref:`custom title<features/argument_processing:Help Messages>`


API Documentation
-----------------

The API documentation is mostly pulled from docstrings in the source code using
the Sphinx `autodoc
<https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`_
extension. However, Sphinx has issues generating documentation for instance
attributes (see `cmd2 issue 821
<https://github.com/python-cmd2/cmd2/issues/821>`_ for the full discussion). We
have chosen to not use code as the source of instance attribute documentation.
Instead, it is added manually to the documentation files in ``cmd2/docs/api``.
See ``cmd2/docs/api/cmd.rst`` to see how to add documentation for an attribute.

For module data members and class attributes, the ``autodoc`` extension allows
documentation in a comment with special formatting (using a #: to start the
comment instead of just #), or in a docstring after the definition. This
project has standardized on the docstring after the definition approach. Do not
use the specially formatted comment approach.

When using the Sphix ``autoclass`` directive, it must be preceded by two blank
lines like so:

.. code-block:: rst

    Classes for storing the history of previously entered commands.


    .. autoclass:: cmd2.history.History
        :members:


    .. autoclass:: cmd2.history.HistoryItem
        :members:


Links to API Reference
----------------------

To reference a method or function, use one of the following approaches:

1. Reference the full dotted path of the method::

     The :meth:`cmd2.Cmd.poutput` method is similar to the Python built-in
     print function.

Which renders as: The :meth:`cmd2.Cmd.poutput` method is similar to the
Python built-in print function.

2. Reference the full dotted path to the method, but only display the method
name::

     The :meth:`~cmd2.Cmd.poutput` method is similar to the Python built-in print function.

Which renders as: The :meth:`~cmd2.Cmd.poutput` method is similar to the
Python built-in print function.

Avoid either of these approaches:

1. Reference just the class name without enough dotted path::

     The :meth:`.Cmd.poutput` method is similar to the Python built-in print
     function.

Because ``cmd2.Cmd`` subclasses ``cmd.Cmd`` from the standard library, this
approach does not clarify which class it is referring to.

2. Reference just a method name::

     The :meth:`poutput` method is similar to the Python built-in print
     function.

While Sphinx may be smart enough to generate the correct output, the potential
for multiple matching references is high, which causes Sphinx to generate
warnings. The build pipeline that renders the documentation treats warnings as
fatal errors. It's best to just be specific about what you are referencing.

See `<https://github.com/python-cmd2/cmd2/issues/821>`_ for the discussion of
how we determined this approach.


Referencing cmd2
-----------------

Whenever you reference ``cmd2`` in the documentation, enclose it in double
backticks. This indicates an inline literal in restructured text, and makes it
stand out when rendered as html.
