# cmd2.utils

## Settings

TODO replace with mkdocstrings:

    > :::: {.autoclass members=""}
    > cmd2.utils.Settable
    >
    > ::: automethod
    > :::
    > ::::

## Quote Handling

TODO replace with mkdocstrings:

    > ::: autofunction
    > cmd2.utils.is[quoted]{#quoted}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.quote[string]{#string}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.quote[string_if_needed]{#string_if_needed}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.strip[quotes]{#quotes}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.quote[specific_tokens]{#specific_tokens}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.unquote[specific_tokens]{#specific_tokens}
    > :::

## IO Handling

TODO replace with mkdocstrings:

    > ::: {.autoclass members=""}
    > cmd2.utils.StdSim
    > :::
    >
    > ::: {.autoclass members=""}
    > cmd2.utils.ByteBuf
    > :::
    >
    > ::: {.autoclass members=""}
    > cmd2.utils.ProcReader
    > :::

## Tab Completion

TODO replace with mkdocstrings:

    > :::::: autoclass
    > cmd2.utils.CompletionMode
    >
    > ::: attribute
    > NONE
    >
    > Tab completion will be disabled during read[input]{#input}() call. Use of custom up-arrow history supported.
    > :::
    >
    > ::: attribute
    > COMMANDS
    >
    > read[input]{#input}() will tab complete cmd2 commands and their arguments. cmd2's command line history will be used for up arrow if history is not provided. Otherwise use of custom up-arrow history supported.
    > :::
    >
    > ::: attribute
    > CUSTOM
    >
    > read[input]{#input}() will tab complete based on one of its following parameters (choices, choices[provider]{#provider}, completer, parser). Use of custom up-arrow history supported
    > :::
    > ::::::
    >
    > :::: autoclass
    > cmd2.utils.CustomCompletionSettings
    >
    > ::: automethod
    > :::
    > ::::

## Text Alignment

TODO replace with mkdocstrings:

    > ::: {.autoclass members="" undoc-members=""}
    > cmd2.utils.TextAlignment
    > :::
    >
    > ::: autofunction
    > cmd2.utils.align[text]{#text}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.align[left]{#left}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.align[right]{#right}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.align[center]{#center}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.truncate[line]{#line}
    > :::

## Miscellaneous

TODO replace with mkdocstrings:

    > ::: autofunction
    > cmd2.utils.to[bool]{#bool}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.categorize
    > :::
    >
    > ::: autofunction
    > cmd2.utils.remove[duplicates]{#duplicates}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.alphabetical[sort]{#sort}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.natural[sort]{#sort}
    > :::
    >
    > ::: autofunction
    > cmd2.utils.suggest[similar]{#similar}
    > :::
