# Theme

`cmd2` provides the ability to configure an overall theme for your application using the
[cmd2.theme.update_theme][] function. This is based on the
[rich.theme](https://rich.readthedocs.io/en/stable/reference/theme.html) container for style
information. You can use this to brand your application and set an overall consistent look and feel
that is appealing to your user base.

## Customizing Completion Menu Colors

`cmd2` leverages `prompt-toolkit` for its tab completion menu. You can customize the colors of the
completion menu by overriding the following styles in your `cmd2` theme:

- `Cmd2Style.COMPLETION_MENU` - Base style for the entire completion menu container (sets the
  background)
- `Cmd2Style.COMPLETION_MENU_COMPLETION` -Style for an individual, non-selected completion item
- `Cmd2Style.COMPLETION_MENU_CURRENT` - Style for the currently selected completion item
- `Cmd2Style.COMPLETION_MENU_META` - Style for "meta" information shown alongside a completion
- `Cmd2Style.COMPLETION_MENU_META_CURRENT`- Style for meta info of current item

By default, the currently selected completion item and metadata are styled with black text on a
green background to provide contrast. All others are left at `prompt-toolkit` defaults by default.
However, `cmd2` application authors are free to customimze these as they see fit in order to match a
desired visual style and/or branding.

## Example

See [rich_theme.py](https://github.com/python-cmd2/cmd2/blob/main/examples/rich_theme.py) for a
simple example of configuring a custom theme for your `cmd2` application.
