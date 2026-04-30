# Theme

`cmd2` provides the ability to configure an overall theme for your application using the
[cmd2.rich_utils.set_theme][] function. This is based on the
[rich.theme](https://rich.readthedocs.io/en/stable/reference/theme.html) container for style
information. You can use this to brand your application and set an overall consistent look and feel
that is appealing to your user base.

## Customizing Completion Menu Colors

`cmd2` leverages `prompt-toolkit` for its tab completion menu. You can customize the colors of the
completion menu by overriding the following styles in your `cmd2` theme:

- `Cmd2Style.COMPLETION_MENU_ITEM`: The background and foreground color of the selected completion
  item.
- `Cmd2Style.COMPLETION_MENU_META`: The background and foreground color of the selected completion
  item's help/meta text.

By default, these are styled with black text on a green background to provide contrast.

## Example

See [rich_theme.py](https://github.com/python-cmd2/cmd2/blob/main/examples/rich_theme.py) for a
simple example of configuring a custom theme for your `cmd2` application.
