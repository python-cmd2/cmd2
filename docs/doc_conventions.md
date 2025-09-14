# Documentation Conventions

## Guiding Principles

Follow the [Documentation Principles](http://www.writethedocs.org/guide/writing/docs-principles/)
described by [Write The Docs](http://www.writethedocs.org)

In addition:

- We have gone to great lengths to retain compatibility with the standard library `cmd`, the
  documentation should make it easy for developers to understand how to move from `cmd` to `cmd2`,
  and what benefits that will provide
- We should provide both descriptive and reference documentation.
- API reference documentation should be generated from docstrings in the code
- Documentation should include rich hyperlinking to other areas of the documentation, and to the API
  reference

## Style Checker

We strongly encourage all developers to use [Prettier](https://prettier.io/) for formatting all
**Markdown** and YAML files. The easiest way to do this is to integrate it with your IDE and
configure your IDE to format on save. You can also install `prettier` either using `npm` or OS
package manager such as `brew` or `apt`.

## Naming Files

All source files in the documentation must:

- have all lower case file names
- if the name has multiple words, separate them with an underscore
- end in '.md'

## Indenting

In Markdown all indenting is significant. Use 4 spaces per indenting level.

## Wrapping

Hard wrap all text so that line lengths are no greater than 100 characters. It makes everything
easier when editing documentation, and has no impact on reading documentation because we render to
html.

## Titles and Headings

Reference the [Markdown Basic Syntax](https://www.markdownguide.org/basic-syntax/) for syntax basics
or [The Markdown Guide](https://www.markdownguide.org/) for a more complete reference.

## Inline Code

Code blocks can be created in two ways:

- Indent the block - this will show as a monospace code block, but won't include highighting
- use the triple backticks followed by the code language, e.g. `python` and close with triple
  backticks

If you want to show non-Python code, like shell commands, then use a different language such as
`javascript`, `shell`, `json`, etc.

## Links

See the [Links](https://www.markdownguide.org/basic-syntax/) Markdown syntax documentation.

## API Documentation

The API documentation is mostly pulled from docstrings in the source code using the MkDocs
[mkdocstrings](https://mkdocstrings.github.io/) plugin.

When using `mkdocstrings`, it must be preceded by a blank line before and after, i.e.:

```markdown
::: cmd2.history.History

::: cmd2.history.HistoryItem
```

### Links to API Reference

To reference a class, method, or function, use block quotes around the name of the full namespace
path for it followed by empty block quotes. So to reference `cmd2.Cmd`, you use `[cmd2.Cmd][]`.

If you want to change the name to use something shorter than the full namespace resolution you can
put the full path in the 2nd set of block quotes instead of leaving it empty and put the shorter
name in the one on the left. So you could also use `[Cmd][cmd2.Cmd]` to link to the API
documentation for `cmd2.Cmd`.

## Referencing cmd2

Whenever you reference `cmd2` in the documentation, enclose it in backticks. This indicates to
Markdown that this words represents code and will stand out when rendered as HTML.
